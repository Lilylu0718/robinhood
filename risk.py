"""纯函数：风控检查。任何 BUY/SELL 下单前必须过 check_risk()。

不发 MCP 请求。规则数值见 config.py。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import config
from data import Portfolio, Position
from strategy import Signal


@dataclass(frozen=True)
class RiskContext:
    portfolio: Portfolio
    positions: dict[str, Position]     # symbol -> Position（当前持仓）
    quotes: dict[str, float]           # symbol -> 最新价
    todays_fills: int                  # 今日已成交订单数
    daily_pnl_pct: float               # 当日组合收益率，例如 -0.021 = -2.1%
    today: date


@dataclass(frozen=True)
class RiskResult:
    signal: Signal
    approved: bool
    order_side: str | None            # "buy" / "sell" / None
    dollar_amount: float | None       # BUY 用金额下单
    quantity: float | None            # SELL 用股数下单（清仓）
    reason: str                       # 风控层的结论说明（会和 signal.reason 一起记日志）


def _min_order_dollars() -> float:
    return 1.0


def stop_loss_signals(ctx: RiskContext) -> list[Signal]:
    """持仓浮亏触及 STOP_LOSS_PCT 的，生成强制 SELL 信号（优先于 MA 信号）。"""
    out = []
    for sym, pos in ctx.positions.items():
        px = ctx.quotes.get(sym)
        if px is None or pos.average_buy_price <= 0:
            continue
        pnl = px / pos.average_buy_price - 1.0
        if pnl <= config.STOP_LOSS_PCT:
            out.append(
                Signal(
                    sym,
                    "SELL",
                    f"止损: 现价 {px:.2f} vs 成本 {pos.average_buy_price:.2f} = {pnl:+.1%} "
                    f"≤ {config.STOP_LOSS_PCT:.0%}",
                )
            )
    return out


def check_risk(signal: Signal, ctx: RiskContext) -> RiskResult:
    """对单个信号做风控裁决。HOLD 直接放行（不下单）。"""
    if signal.action == "HOLD":
        return RiskResult(signal, approved=False, order_side=None,
                          dollar_amount=None, quantity=None, reason="HOLD，不下单")

    is_stop_loss = signal.reason.startswith("止损")

    # 1. 单日交易频率（止损不受此限制——风控离场优先）
    if ctx.todays_fills >= config.MAX_TRADES_PER_DAY and not is_stop_loss:
        return RiskResult(signal, False, None, None, None,
                          f"当日已成交 {ctx.todays_fills} 笔，达上限 {config.MAX_TRADES_PER_DAY}")

    # 2. 单日最大亏损：达标后禁止开仓，允许平仓/止损
    daily_loss_hit = ctx.daily_pnl_pct <= config.MAX_DAILY_LOSS_PCT

    if signal.action == "SELL":
        pos = ctx.positions.get(signal.symbol)
        if pos is None or pos.quantity <= 0:
            return RiskResult(signal, False, None, None, None,
                              "无持仓，SELL 信号忽略")
        return RiskResult(signal, True, "sell", None, pos.quantity,
                          "止损清仓" if is_stop_loss else "死叉清仓")

    # signal.action == "BUY"
    if daily_loss_hit:
        return RiskResult(signal, False, None, None, None,
                          f"当日亏损 {ctx.daily_pnl_pct:+.1%} ≤ {config.MAX_DAILY_LOSS_PCT:.0%}，停止开仓")

    px = ctx.quotes.get(signal.symbol)
    if px is None:
        return RiskResult(signal, False, None, None, None, "无最新价，无法定量下单")

    total = ctx.portfolio.total_value
    cur_pos = ctx.positions.get(signal.symbol)
    cur_val = (cur_pos.quantity * px) if cur_pos else 0.0

    cap_room = config.MAX_POSITION_PCT * total - cur_val      # 距 25% 上限还能买多少
    if cap_room <= _min_order_dollars():
        return RiskResult(signal, False, None, None, None,
                          f"{signal.symbol} 已达/接近 {config.MAX_POSITION_PCT:.0%} 仓位上限"
                          f"（现值 {cur_val:.0f} / 总值 {total:.0f}）")

    target = config.TARGET_POSITION_PCT * total
    dollars = min(target, cap_room, ctx.portfolio.buying_power)

    if dollars <= _min_order_dollars():
        return RiskResult(signal, False, None, None, None,
                          f"可下单金额 {dollars:.2f} 过小（购买力 {ctx.portfolio.buying_power:.2f}）")

    return RiskResult(signal, True, "buy", round(dollars, 2), None,
                      f"开仓 ${dollars:.2f}（目标 {config.TARGET_POSITION_PCT:.0%}，"
                      f"仓位上限余量 ${cap_room:.0f}，购买力 ${ctx.portfolio.buying_power:.0f}）")
