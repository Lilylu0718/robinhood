import pytest

import config
import executor
from data import Portfolio
from risk import RiskResult
from strategy import Signal


def _rr_buy():
    return RiskResult(Signal("NVDA", "BUY", "金叉"), True, "buy", 200.0, None, "开仓 $200")


def _rr_sell():
    return RiskResult(Signal("NVDA", "SELL", "死叉"), True, "sell", None, 1.5, "死叉清仓")


def test_assert_account_safe_blocks_forbidden():
    for bad in config.FORBIDDEN_ACCOUNTS:
        with pytest.raises(executor.AccountSafetyError):
            executor.assert_account_safe(bad)


def test_assert_account_safe_blocks_unknown():
    with pytest.raises(executor.AccountSafetyError):
        executor.assert_account_safe("999999999")


def test_assert_account_safe_allows_experiment():
    executor.assert_account_safe(config.ACCOUNT_NUMBER)  # no raise


def test_build_order_plan_buy():
    plan = executor.build_order_plan(_rr_buy())
    assert plan.account_number == config.ACCOUNT_NUMBER
    assert plan.side == "buy" and plan.dollar_amount == "200.00" and plan.quantity is None
    kw = plan.as_mcp_kwargs()
    assert kw["type"] == "market" and kw["dollar_amount"] == "200.00"
    assert "ref_id" in kw and len(kw["ref_id"]) == 36


def test_build_order_plan_sell_uses_quantity():
    plan = executor.build_order_plan(_rr_sell())
    assert plan.side == "sell" and plan.quantity == "1.5" and plan.dollar_amount is None


def test_build_order_plan_rejects_unapproved():
    rr = RiskResult(Signal("QQQ", "HOLD", "x"), False, None, None, None, "HOLD")
    with pytest.raises(ValueError):
        executor.build_order_plan(rr)


def test_execute_dry_run_prints_and_no_plan(capsys):
    state, payload = executor.execute(_rr_buy(), dry_run=True)
    assert state == "dry_run"
    assert "DRY_RUN" in capsys.readouterr().out


def test_execute_real_returns_plan():
    state, payload = executor.execute(_rr_buy(), dry_run=False)
    assert state == "needs_mcp" and isinstance(payload, executor.OrderPlan)


def test_execute_skipped_when_not_approved():
    rr = RiskResult(Signal("QQQ", "HOLD", "x"), False, None, None, None, "HOLD，不下单")
    state, payload = executor.execute(rr, dry_run=False)
    assert state == "skipped"
