"""纯函数：抄底（均值回归）信号 + 财报避雷。2026-11-02 起替换原 MA10/MA30 趋势策略（用户偏好追跌抄底）。

入场（BUY，未持仓）：收盘价较近 DIP_LOOKBACK 日最高收盘回撤 ≥ 阈值（个股 / ETF 分开）
                     且 RSI(14) ≤ DIP_RSI_MAX，且不在财报避雷窗口内。
核心大厂（config.CORE_SYMBOLS）：永不 SELL；已持有时仅在比成本再低 ≥8% 且仍满足抄底形态时加仓。
                   另外 Claude 每日研判可额外发起核心股 BUY（run_once.py --judgment）。
离场（SELL，卫星持仓）：浮盈 ≥ TAKE_PROFIT_PCT（止盈），
                     或 收盘重新站上 MA20 且浮盈 ≥ REBOUND_MIN_PROFIT_PCT（反弹完成）。
止损由 risk.stop_loss_signals 负责（config.STOP_LOSS_PCT）。
Signal.score 越小越优先（= RSI），同一天多个 BUY 时 main.py 按它排序，配合每日交易上限。
不发 MCP 请求。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

import config
from data import EarningsEvent, next_earnings


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: str          # "BUY" / "SELL" / "HOLD"
    reason: str
    fast_ma: float | None = None   # 历史字段名保留（logger 用）；现在存 RSI
    slow_ma: float | None = None   # 现在存 MA20
    score: float | None = None     # BUY 排序用，越小越优先


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI。"""
    d = closes.diff()
    up = d.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / dn.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100.0)


def indicators(closes: pd.Series) -> tuple[float, float, float, float]:
    """返回 (close, 距 N 日最高收盘回撤, RSI, MA20)。"""
    need = max(config.DIP_LOOKBACK, config.RSI_PERIOD, config.REBOUND_MA) + 1
    if len(closes) < need:
        raise ValueError(f"需要至少 {need} 根收盘价，只有 {len(closes)}")
    c = float(closes.iloc[-1])
    hi = float(closes.iloc[-config.DIP_LOOKBACK:].max())
    r = float(rsi(closes, config.RSI_PERIOD).iloc[-1])
    ma = float(closes.iloc[-config.REBOUND_MA:].mean())
    return c, c / hi - 1.0, r, ma


def dip_threshold(symbol: str) -> float:
    return config.DIP_DRAWDOWN_ETF if symbol in config.ETF_SYMBOLS else config.DIP_DRAWDOWN_STOCK


def generate_signal(
    symbol: str,
    df: pd.DataFrame,
    earnings: list[EarningsEvent],
    today: date,
    holding: bool = False,
    avg_cost: float | None = None,
    price: float | None = None,
) -> Signal:
    """price：实时价（有则用于盈亏判断，否则用最后收盘）。avg_cost：持仓成本。"""
    try:
        close, dd, r, ma = indicators(df["close"])
    except ValueError as e:
        return Signal(symbol, "HOLD", f"数据不足: {e}")

    px = price if price else close
    base = (f"收盘 {close:.2f} | 距{config.DIP_LOOKBACK}日高 {dd:+.1%} | "
            f"RSI {r:.0f} | MA{config.REBOUND_MA} {ma:.2f}")

    th = dip_threshold(symbol)
    is_dip = dd <= -th and r <= config.DIP_RSI_MAX

    # ── 核心大厂：只买不卖。已持有时只在比成本再低 ≥8% 且仍是抄底形态时加仓 ─────
    if symbol in config.CORE_SYMBOLS and holding:
        if not avg_cost or avg_cost <= 0:
            return Signal(symbol, "HOLD", f"核心持有（无成本价）| {base}", r, ma)
        pnl = px / avg_cost - 1.0
        if is_dip and pnl <= -config.CORE_ADD_BELOW_COST_PCT:
            return Signal(symbol, "BUY", f"核心加仓: 低于成本 {pnl:+.1%} 且抄底形态 | {base}", r, ma, score=r)
        return Signal(symbol, "HOLD", f"核心长期持有（浮盈 {pnl:+.1%}，不卖）| {base}", r, ma)

    # ── 离场（卫星）──────────────────────────────────────────────────
    if holding:
        if not avg_cost or avg_cost <= 0:
            return Signal(symbol, "HOLD", f"持仓但无成本价，需人工检查 | {base}", r, ma)
        pnl = px / avg_cost - 1.0
        if pnl >= config.TAKE_PROFIT_PCT:
            return Signal(symbol, "SELL", f"止盈: 浮盈 {pnl:+.1%} ≥ {config.TAKE_PROFIT_PCT:.0%} | {base}", r, ma)
        if px >= ma and pnl >= config.REBOUND_MIN_PROFIT_PCT:
            return Signal(symbol, "SELL",
                          f"反弹完成: 价 ≥ MA{config.REBOUND_MA} 且浮盈 {pnl:+.1%} | {base}", r, ma)
        return Signal(symbol, "HOLD", f"持仓等反弹（浮盈 {pnl:+.1%}）| {base}", r, ma)

    # ── 入场 ──────────────────────────────────────────────────────────
    if is_dip:
        ev = next_earnings(earnings, today, config.EARNINGS_TREAT_TENTATIVE_AS_REAL)
        if ev is not None:
            days_to = (ev.report_date - today).days
            if 0 <= days_to <= config.EARNINGS_BLACKOUT_DAYS:
                tag = "" if ev.verified else "(未确认)"
                return Signal(symbol, "HOLD",
                              f"抄底信号但财报避雷: {ev.report_date}{tag} 还有 {days_to} 天 | {base}", r, ma)
        return Signal(symbol, "BUY", f"抄底: 回撤 ≥ {th:.0%} 且 RSI ≤ {config.DIP_RSI_MAX} | {base}",
                      r, ma, score=r)

    why = []
    if dd > -th:
        why.append(f"回撤未到 {th:.0%}")
    if r > config.DIP_RSI_MAX:
        why.append(f"RSI 未到 {config.DIP_RSI_MAX}")
    return Signal(symbol, "HOLD", f"未持仓，不抄（{'、'.join(why)}）| {base}", r, ma)


def generate_signals(
    dfs: dict[str, pd.DataFrame],
    earnings_by_sym: dict[str, list[EarningsEvent]],
    today: date,
    held_symbols: set[str] | None = None,
    symbols: tuple[str, ...] = config.SYMBOLS,
    avg_costs: dict[str, float] | None = None,
    quotes: dict[str, float] | None = None,
) -> list[Signal]:
    held = held_symbols or set()
    avg_costs = avg_costs or {}
    quotes = quotes or {}
    out = []
    for s in symbols:
        if s not in dfs:
            msg = "无价格数据（MCP 拉取失败），持仓中——需人工检查" if s in held else "无价格数据（MCP 拉取失败或跳过）"
            out.append(Signal(s, "HOLD", msg))
            continue
        out.append(generate_signal(s, dfs[s], earnings_by_sym.get(s, []), today,
                                   holding=s in held, avg_cost=avg_costs.get(s), price=quotes.get(s)))
    return out
