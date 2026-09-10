from datetime import date

import pytest

import config
from data import Portfolio, Position
from risk import RiskContext, check_risk, stop_loss_signals
from strategy import Signal


def ctx(**kw):
    base = dict(
        portfolio=Portfolio(total_value=1000.0, cash=1000.0, buying_power=1000.0),
        positions={},
        quotes={"NVDA": 200.0, "MU": 1000.0},
        todays_fills=0,
        daily_pnl_pct=0.0,
        today=date(2026, 9, 10),
    )
    base.update(kw)
    return RiskContext(**base)


BUY = Signal("NVDA", "BUY", "金叉")
SELL = Signal("NVDA", "SELL", "死叉")


def test_buy_sizing_respects_target_and_cap():
    rr = check_risk(BUY, ctx())
    assert rr.approved and rr.order_side == "buy"
    # target 20% of 1000 = 200
    assert rr.dollar_amount == pytest.approx(200.0)


def test_buy_blocked_when_position_at_cap():
    # 已持 NVDA 市值 260 > 25% * 1000
    c = ctx(positions={"NVDA": Position("NVDA", 1.3, 180.0)})  # 1.3 * 200 = 260
    rr = check_risk(BUY, c)
    assert not rr.approved and "仓位上限" in rr.reason


def test_buy_limited_by_buying_power():
    c = ctx(portfolio=Portfolio(1000.0, 50.0, 50.0))
    rr = check_risk(BUY, c)
    assert rr.approved and rr.dollar_amount == pytest.approx(50.0)


def test_daily_loss_halts_new_buys_but_not_sells():
    c = ctx(daily_pnl_pct=-0.031, positions={"NVDA": Position("NVDA", 1.0, 210.0)})
    assert not check_risk(BUY, c).approved
    assert check_risk(SELL, c).approved


def test_daily_trade_limit_blocks_non_stoploss():
    c = ctx(todays_fills=2)
    assert not check_risk(BUY, c).approved
    # 止损不受频率限制
    sl = Signal("NVDA", "SELL", "止损: ...")
    c2 = ctx(todays_fills=2, positions={"NVDA": Position("NVDA", 1.0, 210.0)})
    assert check_risk(sl, c2).approved


def test_sell_without_position_ignored():
    rr = check_risk(SELL, ctx())
    assert not rr.approved and "无持仓" in rr.reason


def test_stop_loss_triggers_below_threshold():
    c = ctx(quotes={"NVDA": 100.0}, positions={"NVDA": Position("NVDA", 1.0, 110.0)})
    sigs = stop_loss_signals(c)
    assert len(sigs) == 1 and sigs[0].action == "SELL" and "止损" in sigs[0].reason


def test_stop_loss_not_triggered_within_threshold():
    c = ctx(quotes={"NVDA": 106.0}, positions={"NVDA": Position("NVDA", 1.0, 110.0)})
    assert stop_loss_signals(c) == []


def test_hold_never_orders():
    rr = check_risk(Signal("QQQ", "HOLD", "无交叉"), ctx())
    assert not rr.approved and rr.order_side is None
