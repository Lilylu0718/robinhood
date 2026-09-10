"""下单执行层。

DRY_RUN=True：只打印，返回 dry_run 结果。绝不下真实单。
DRY_RUN=False：executor **不直接调 MCP**（Python 调不到）。它产出一个 OrderPlan，
                Claude 在会话里按 plan 调 review_equity_order → place_equity_order，
                再把结果回填。所有真实下单前 assert_account_safe 必须通过。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import config
from risk import RiskResult


class AccountSafetyError(RuntimeError):
    pass


def assert_account_safe(account_number: str) -> None:
    """任何下单动作前调用。账户不是实验账户就炸，绝不误碰主账户。"""
    if account_number in config.FORBIDDEN_ACCOUNTS:
        raise AccountSafetyError(
            f"账户 {account_number} 在禁止清单里（主账户/其它账户），拒绝下单"
        )
    if account_number != config.ACCOUNT_NUMBER:
        raise AccountSafetyError(
            f"账户 {account_number} != 实验账户 {config.ACCOUNT_NUMBER}，拒绝下单"
        )


@dataclass(frozen=True)
class OrderPlan:
    """交给 Claude 去调 MCP 的下单计划。"""
    account_number: str
    symbol: str
    side: str                       # "buy" / "sell"
    order_type: str                 # 固定 "market"（本策略只用市价单，含分数股）
    dollar_amount: str | None       # buy：金额字符串，如 "200.00"
    quantity: str | None            # sell：股数字符串（清仓）
    ref_id: str                     # 幂等键
    market_hours: str = "regular_hours"

    def as_mcp_kwargs(self) -> dict:
        kw = {
            "account_number": self.account_number,
            "symbol": self.symbol,
            "side": self.side,
            "type": self.order_type,
            "market_hours": self.market_hours,
            "ref_id": self.ref_id,
        }
        if self.dollar_amount is not None:
            kw["dollar_amount"] = self.dollar_amount
        if self.quantity is not None:
            kw["quantity"] = self.quantity
        return kw


def build_order_plan(rr: RiskResult, account_number: str = config.ACCOUNT_NUMBER) -> OrderPlan:
    if not rr.approved or rr.order_side is None:
        raise ValueError("RiskResult 未批准，不能建 OrderPlan")
    assert_account_safe(account_number)
    return OrderPlan(
        account_number=account_number,
        symbol=rr.signal.symbol,
        side=rr.order_side,
        order_type="market",
        dollar_amount=None if rr.dollar_amount is None else f"{rr.dollar_amount:.2f}",
        quantity=None if rr.quantity is None else f"{rr.quantity}",
        ref_id=str(uuid.uuid4()),
    )


def dry_run_line(rr: RiskResult) -> str:
    s = rr.signal
    if not rr.approved:
        return f"[DRY_RUN] {s.symbol} {s.action} → 不下单：{rr.reason}"
    if rr.order_side == "buy":
        return f"[DRY_RUN] {s.symbol} BUY 市价 ${rr.dollar_amount:.2f} —— {rr.reason}"
    return f"[DRY_RUN] {s.symbol} SELL 市价 {rr.quantity} 股（清仓）—— {rr.reason}"


def execute(rr: RiskResult, *, dry_run: bool = config.DRY_RUN):
    """DRY_RUN 分支：打印并返回 (state, notes)。
    真实分支：返回 OrderPlan，由调用方（Claude）走 review→place。
    """
    if not rr.approved:
        return "skipped", rr.reason

    if dry_run:
        line = dry_run_line(rr)
        print(line)
        return "dry_run", line

    return "needs_mcp", build_order_plan(rr)
