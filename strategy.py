"""纯函数：技术面信号（MA10/MA30）+ 财报避雷。

入场（BUY）是事件驱动：只在"刚发生金叉"那根 bar 触发，不追高。
离场（SELL）是状态驱动：**只要持仓且 MA10 < MA30 就离场**，不等新的死叉——
    漏跑一天不会把我们困在亏损仓位里干等 -6% 止损。
不发 MCP 请求。输入是 data.py 解析好的结构，输出带 reason 的信号。
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
    fast_ma: float | None = None
    slow_ma: float | None = None


def _ma_cross(closes: pd.Series, fast: int, slow: int) -> tuple[str, float, float]:
    """返回 (cross, fast_ma_today, slow_ma_today)。
    cross ∈ {"golden", "death", "none"}，看最后一根 bar 相对前一根 bar 的 fast-slow 关系翻转。
    """
    if len(closes) < slow + 1:
        raise ValueError(f"需要至少 {slow + 1} 根收盘价，只有 {len(closes)}")
    fast_ma = closes.rolling(fast).mean()
    slow_ma = closes.rolling(slow).mean()
    d_now = fast_ma.iloc[-1] - slow_ma.iloc[-1]
    d_prev = fast_ma.iloc[-2] - slow_ma.iloc[-2]
    if d_prev <= 0 < d_now:
        cross = "golden"
    elif d_prev >= 0 > d_now:
        cross = "death"
    else:
        cross = "none"
    return cross, float(fast_ma.iloc[-1]), float(slow_ma.iloc[-1])


def generate_signal(
    symbol: str,
    df: pd.DataFrame,
    earnings: list[EarningsEvent],
    today: date,
    holding: bool = False,
) -> Signal:
    """单个标的的信号。df: data.parse_historicals 的某个 symbol 的 DataFrame。
    holding: 当前是否持有该标的（决定用离场逻辑还是入场逻辑）。
    """
    try:
        cross, fast_ma, slow_ma = _ma_cross(df["close"], config.MA_FAST, config.MA_SLOW)
    except ValueError as e:
        return Signal(symbol, "HOLD", f"数据不足: {e}")

    base = f"MA{config.MA_FAST}={fast_ma:.2f} MA{config.MA_SLOW}={slow_ma:.2f}"
    below = fast_ma < slow_ma

    # ── 离场：状态驱动。持仓 + 空头排列 → 清仓（不等新死叉）──────────
    if holding:
        if below:
            note = "死叉离场" if cross == "death" else "空头排列离场"
            return Signal(symbol, "SELL", f"{note}: MA{config.MA_FAST} < MA{config.MA_SLOW} | {base}",
                          fast_ma, slow_ma)
        return Signal(symbol, "HOLD", f"持仓续持（多头排列）| {base}", fast_ma, slow_ma)

    # ── 入场：事件驱动。仅"刚发生金叉"那根 bar ────────────────────────
    if cross == "golden":
        ev = next_earnings(earnings, today, config.EARNINGS_TREAT_TENTATIVE_AS_REAL)
        if ev is not None:
            days_to = (ev.report_date - today).days
            if 0 <= days_to <= config.EARNINGS_BLACKOUT_DAYS:
                tag = "" if ev.verified else "(未确认)"
                return Signal(
                    symbol, "HOLD",
                    f"金叉但财报避雷: {ev.report_date}{tag} 还有 {days_to} 天，暂缓开仓 | {base}",
                    fast_ma, slow_ma,
                )
        return Signal(symbol, "BUY", f"金叉: MA{config.MA_FAST} 上穿 MA{config.MA_SLOW} | {base}",
                      fast_ma, slow_ma)

    trend = "多头" if not below else "空头"
    return Signal(symbol, "HOLD", f"未持仓，无金叉（{trend}排列）| {base}", fast_ma, slow_ma)


def generate_signals(
    dfs: dict[str, pd.DataFrame],
    earnings_by_sym: dict[str, list[EarningsEvent]],
    today: date,
    held_symbols: set[str] | None = None,
    symbols: tuple[str, ...] = config.SYMBOLS,
) -> list[Signal]:
    held = held_symbols or set()
    out = []
    for s in symbols:
        if s not in dfs:
            # 没数据：持仓的标记为需人工看，未持仓的 HOLD
            msg = "无价格数据（MCP 拉取失败），持仓中——需人工检查" if s in held else "无价格数据（MCP 拉取失败或跳过）"
            out.append(Signal(s, "HOLD", msg))
            continue
        out.append(
            generate_signal(s, dfs[s], earnings_by_sym.get(s, []), today, holding=s in held)
        )
    return out
