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
        quotes={"MU": 200.0, "MU": 1000.0},
        todays_fills=0,
        daily_pnl_pct=0.0,
        today=date(2026, 9, 10),
    )
    base.update(kw)
    return RiskContext(**base)


BUY = Signal("MU", "BUY", "金叉")
SELL = Signal("MU", "SELL", "死叉")


def test_buy_sizing_respects_target_and_cap():
    rr = check_risk(BUY, ctx())
    assert rr.approved and rr.order_side == "buy"
    # target 20% of 1000 = 200
    assert rr.dollar_amount == pytest.approx(200.0)


def test_buy_blocked_when_position_at_cap():
    # 已持 NVDA 市值 260 > 25% * 1000
    c = ctx(positions={"MU": Position("MU", 1.3, 180.0)})  # 1.3 * 200 = 260
    rr = check_risk(BUY, c)
    assert not rr.approved and "仓位上限" in rr.reason


def test_buy_limited_by_buying_power():
    c = ctx(portfolio=Portfolio(1000.0, 50.0, 50.0))
    rr = check_risk(BUY, c)
    assert rr.approved and rr.dollar_amount == pytest.approx(50.0)


def test_daily_loss_halts_new_buys_but_not_sells():
    c = ctx(daily_pnl_pct=-0.031, positions={"MU": Position("MU", 1.0, 210.0)})
    assert not check_risk(BUY, c).approved
    assert check_risk(SELL, c).approved


def test_daily_trade_limit_blocks_non_stoploss():
    c = ctx(todays_fills=config.MAX_TRADES_PER_DAY)
    assert not check_risk(BUY, c).approved
    # 止损不受频率限制
    sl = Signal("MU", "SELL", "止损: ...")
    c2 = ctx(todays_fills=config.MAX_TRADES_PER_DAY, positions={"MU": Position("MU", 1.0, 210.0)})
    assert check_risk(sl, c2).approved


def test_sell_without_position_ignored():
    rr = check_risk(SELL, ctx())
    assert not rr.approved and "无持仓" in rr.reason


def test_stop_loss_triggers_below_threshold():
    c = ctx(quotes={"QQQ": 100.0}, positions={"QQQ": Position("QQQ", 1.0, 120.0)})
    sigs = stop_loss_signals(c)
    assert len(sigs) == 1 and sigs[0].action == "SELL" and "止损" in sigs[0].reason


def test_stop_loss_not_triggered_within_threshold():
    c = ctx(quotes={"MU": 106.0}, positions={"MU": Position("MU", 1.0, 110.0)})
    assert stop_loss_signals(c) == []


def test_hold_never_orders():
    rr = check_risk(Signal("QQQ", "HOLD", "无交叉"), ctx())
    assert not rr.approved and rr.order_side is None


def test_long_term_hold_never_stopped_out():
    c = ctx(quotes={"PURR": 5.0}, positions={"PURR": Position("PURR", 1.0, 13.8)})
    assert stop_loss_signals(c) == []


def test_core_symbols_never_stopped_out():
    c = ctx(quotes={"GOOGL": 50.0}, positions={"GOOGL": Position("GOOGL", 1.0, 100.0)})
    assert stop_loss_signals(c) == []


def test_core_buy_sized_smaller_and_ignores_daily_loss():
    c = ctx(daily_pnl_pct=-0.05, quotes={"GOOGL": 100.0})
    rr = check_risk(Signal("GOOGL", "BUY", "抄底"), c)
    assert rr.approved and rr.dollar_amount == 100.0


def test_mu_kept_no_stop_loss():
    c = ctx(quotes={"MU": 600.0}, positions={"MU": Position("MU", 1.0, 854.0)})
    assert stop_loss_signals(c) == []
