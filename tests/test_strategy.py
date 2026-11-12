from datetime import date

import pandas as pd

from data import EarningsEvent
from strategy import generate_signal, generate_signals, indicators

# 30 天平在 100，然后 10 天每天跌 1.5% → 回撤 ~14%，RSI 很低
CRASH = [100.0] * 30 + [100.0 * (0.985 ** i) for i in range(1, 11)]
FLAT = [100.0] * 40
# 小跌 3%：回撤不够
SMALL_DIP = [100.0] * 30 + [100.0 - 0.3 * i for i in range(1, 11)]
# 先跌后反弹到 MA20 之上
REBOUND = [100.0] * 30 + [90.0] * 5 + [100.0] * 5

D = date(2026, 2, 10)


def _df(closes):
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="D").date
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1] * len(closes)}, index=idx)


def test_indicators_on_crash():
    c, dd, r, ma = indicators(_df(CRASH)["close"])
    assert dd < -0.13 and r < 20 and c < ma


def test_buy_on_deep_oversold_dip():
    s = generate_signal("NVDA", _df(CRASH), [], D)
    assert s.action == "BUY" and "抄底" in s.reason and s.score is not None


def test_no_buy_when_flat():
    assert generate_signal("NVDA", _df(FLAT), [], D).action == "HOLD"


def test_no_buy_when_dip_too_small_for_stock():
    s = generate_signal("NVDA", _df(SMALL_DIP), [], D)
    assert s.action == "HOLD" and "回撤未到" in s.reason


def test_etf_uses_smaller_threshold():
    # 回撤 ~6%，RSI 低：个股不买，QQQ 买
    six = [100.0] * 30 + [100.0 - 0.6 * i for i in range(1, 11)]
    assert generate_signal("NVDA", _df(six), [], D).action == "HOLD"
    assert generate_signal("QQQ", _df(six), [], D).action == "BUY"


def test_earnings_blackout_suppresses_buy():
    ev = [EarningsEvent("NVDA", date(2026, 2, 11), "pm", True, False)]
    s = generate_signal("NVDA", _df(CRASH), ev, D)
    assert s.action == "HOLD" and "财报避雷" in s.reason


def test_take_profit_when_holding():
    s = generate_signal("MU", _df(FLAT), [], D, holding=True, avg_cost=90.0)
    assert s.action == "SELL" and "止盈" in s.reason


def test_rebound_exit_when_above_ma_and_profitable():
    s = generate_signal("MU", _df(REBOUND), [], D, holding=True, avg_cost=95.0)
    assert s.action == "SELL" and "反弹完成" in s.reason


def test_hold_when_holding_underwater():
    s = generate_signal("MU", _df(CRASH), [], D, holding=True, avg_cost=95.0)
    assert s.action == "HOLD" and "等反弹" in s.reason


def test_live_price_used_for_pnl():
    s = generate_signal("MU", _df(FLAT), [], D, holding=True, avg_cost=100.0, price=111.0)
    assert s.action == "SELL" and "止盈" in s.reason


def test_holding_without_cost_holds():
    s = generate_signal("MU", _df(FLAT), [], D, holding=True, avg_cost=None)
    assert s.action == "HOLD" and "人工" in s.reason


def test_insufficient_data_holds():
    s = generate_signal("NVDA", _df([100.0] * 10), [], D)
    assert s.action == "HOLD" and "数据不足" in s.reason


def test_missing_data_symbol_holds():
    sigs = generate_signals({}, {}, D, symbols=("NVDA",))
    assert sigs[0].action == "HOLD" and "无价格数据" in sigs[0].reason


# ── 核心大厂 ──────────────────────────────────────────────────────────
def test_core_never_sells_even_with_big_profit():
    s = generate_signal("GOOGL", _df(FLAT), [], D, holding=True, avg_cost=50.0)
    assert s.action == "HOLD" and "不卖" in s.reason


def test_core_adds_only_well_below_cost():
    assert generate_signal("GOOGL", _df(CRASH), [], D, holding=True, avg_cost=90.0).action == "HOLD"
    s = generate_signal("GOOGL", _df(CRASH), [], D, holding=True, avg_cost=100.0)
    assert s.action == "BUY" and "核心加仓" in s.reason


def test_judgment_buy_skip_and_satellite_sell():
    from main import apply_judgments
    from strategy import Signal
    sigs = [Signal("GOOGL", "HOLD", "x"), Signal("MU", "HOLD", "x"), Signal("QQQ", "BUY", "x")]
    errs = []
    out = apply_judgments(sigs, [
        {"symbol": "GOOGL", "action": "BUY", "reason": "财报后错杀"},
        {"symbol": "MU", "action": "BUY", "reason": "错杀"},
        {"symbol": "QQQ", "action": "SKIP", "reason": "宏观风险"},
        {"symbol": "GOOGL", "action": "SELL", "reason": "核心不许卖"},
        {"symbol": "TSLA", "action": "BUY", "reason": "不在池"},
    ], errs)
    assert [s.action for s in out] == ["BUY", "BUY", "HOLD"]
    assert out[0].reason.startswith("判断") and len(errs) == 2


def test_judgment_sell_only_held_satellite_not_long_term():
    from main import apply_judgments
    from strategy import Signal
    sigs = [Signal("QQQ", "HOLD", "x"), Signal("MU", "HOLD", "x"), Signal("NVDA", "HOLD", "x")]
    j = [{"symbol": s, "action": "SELL", "reason": "论点破了"} for s in ("QQQ", "MU", "NVDA")]
    errs = []
    out = apply_judgments(sigs, j, errs, held={"QQQ", "MU", "NVDA"})
    assert [s.action for s in out] == ["SELL", "HOLD", "HOLD"] and len(errs) == 2
    assert apply_judgments(sigs, j[:1], [], held=set())[0].action == "HOLD"


def test_live_bar_appended_only_when_stale():
    from main import with_live_bar
    df = _df(FLAT)                      # 最后一根 2026-02-09
    out = with_live_bar({"MU": df}, {"MU": 90.0}, date(2026, 2, 10))["MU"]
    assert len(out) == len(df) + 1 and out["close"].iloc[-1] == 90.0
    same = with_live_bar({"MU": df}, {"MU": 90.0}, df.index[-1])["MU"]
    assert len(same) == len(df)
