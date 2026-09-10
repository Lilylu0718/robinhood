from datetime import date

import pandas as pd
import pytest

import config
from data import EarningsEvent
from strategy import generate_signal, _ma_cross

# 交叉发生在最后一根 bar：前 40 根平在 100（快线=慢线），最后一根跳变。
GOLDEN = [100.0] * 40 + [102.0]
DEATH = [100.0] * 40 + [98.0]
FLAT = [100.0] * 41
# 空头排列但交叉早已发生（不是最后一根）
BELOW_NO_CROSS = [100.0] * 20 + [90.0] * 21
# 多头排列但金叉早已发生
ABOVE_NO_CROSS = [90.0] * 20 + [100.0] * 21


def _df(closes):
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="D").date
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1] * len(closes)}, index=idx)


D = date(2026, 2, 10)


# ── _ma_cross ────────────────────────────────────────────────────────
def test_golden_cross_detected():
    cross, f, s = _ma_cross(pd.Series(GOLDEN), config.MA_FAST, config.MA_SLOW)
    assert cross == "golden" and f > s


def test_death_cross_detected():
    cross, f, s = _ma_cross(pd.Series(DEATH), config.MA_FAST, config.MA_SLOW)
    assert cross == "death" and f < s


def test_no_cross_on_flat():
    assert _ma_cross(pd.Series(FLAT), config.MA_FAST, config.MA_SLOW)[0] == "none"


def test_below_no_cross_is_none():
    assert _ma_cross(pd.Series(BELOW_NO_CROSS), config.MA_FAST, config.MA_SLOW)[0] == "none"


# ── 入场（未持仓）：事件驱动，只认新金叉 ─────────────────────────────
def test_buy_on_fresh_golden_cross():
    sig = generate_signal("NVDA", _df(GOLDEN), [], D, holding=False)
    assert sig.action == "BUY" and "金叉" in sig.reason


def test_no_buy_when_above_but_no_fresh_cross():
    sig = generate_signal("NVDA", _df(ABOVE_NO_CROSS), [], D, holding=False)
    assert sig.action == "HOLD" and "无金叉" in sig.reason


def test_no_action_when_below_and_not_holding():
    sig = generate_signal("NVDA", _df(BELOW_NO_CROSS), [], D, holding=False)
    assert sig.action == "HOLD"


def test_earnings_blackout_suppresses_buy():
    df = _df(GOLDEN)
    today = df.index[-1]
    ev = [EarningsEvent("NVDA", date(today.year, today.month, today.day), "pm", True, False)]
    sig = generate_signal("NVDA", df, ev, today, holding=False)
    assert sig.action == "HOLD" and "财报避雷" in sig.reason


def test_tentative_earnings_respected_when_configured(monkeypatch):
    df = _df(GOLDEN)
    today = df.index[-1]
    ev = [EarningsEvent("NVDA", date(today.year, today.month, today.day), "pm", False, False)]
    monkeypatch.setattr(config, "EARNINGS_TREAT_TENTATIVE_AS_REAL", True)
    assert generate_signal("NVDA", df, ev, today, holding=False).action == "HOLD"
    monkeypatch.setattr(config, "EARNINGS_TREAT_TENTATIVE_AS_REAL", False)
    assert generate_signal("NVDA", df, ev, today, holding=False).action == "BUY"


# ── 离场（持仓）：状态驱动，MA10 < MA30 就走 ─────────────────────────
def test_sell_when_holding_and_fresh_death_cross():
    sig = generate_signal("MU", _df(DEATH), [], D, holding=True)
    assert sig.action == "SELL" and "死叉离场" in sig.reason


def test_sell_when_holding_and_below_even_without_fresh_cross():
    sig = generate_signal("MU", _df(BELOW_NO_CROSS), [], D, holding=True)
    assert sig.action == "SELL" and "空头排列离场" in sig.reason


def test_hold_when_holding_and_still_bullish():
    sig = generate_signal("MU", _df(ABOVE_NO_CROSS), [], D, holding=True)
    assert sig.action == "HOLD" and "续持" in sig.reason


def test_earnings_blackout_does_not_block_exit():
    df = _df(DEATH)
    today = df.index[-1]
    ev = [EarningsEvent("MU", date(today.year, today.month, today.day), "pm", True, False)]
    sig = generate_signal("MU", df, ev, today, holding=True)
    assert sig.action == "SELL"


def test_insufficient_data_holds():
    sig = generate_signal("AVGO", _df([100.0] * 10), [], D)
    assert sig.action == "HOLD" and "数据不足" in sig.reason
