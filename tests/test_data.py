import json
from datetime import date
from pathlib import Path

import pytest

import data

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def hist():
    return json.loads((FIX / "historicals_day_4syms.json").read_text())


@pytest.fixture
def earn():
    return json.loads((FIX / "earnings_calendar_sample.json").read_text())


def test_parse_historicals_shape(hist):
    dfs = data.parse_historicals(hist)
    assert set(dfs) == {"AVGO", "NVDA", "MU", "QQQ"}
    df = dfs["NVDA"]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.is_monotonic_increasing
    assert len(df) == 70
    assert df["close"].iloc[-1] == pytest.approx(223.67)


def test_parse_earnings_filters_pool(earn):
    by = data.parse_earnings_calendar(earn, ("AVGO", "NVDA", "MU", "QQQ"))
    assert [e.report_date for e in by["MU"]] == [date(2026, 9, 30)]
    assert by["MU"][0].verified is True
    assert by["MU"][0].reported is False
    assert by["QQQ"] == []
    # AVGO row has eps.actual set -> reported
    assert by["AVGO"][0].reported is True


def test_next_earnings_skips_reported_and_past(earn):
    by = data.parse_earnings_calendar(earn, ("AVGO", "NVDA", "MU"))
    # AVGO already reported -> None
    assert data.next_earnings(by["AVGO"], date(2026, 9, 10), True) is None
    # NVDA tentative: respected only when treat_tentative_as_real=True
    assert data.next_earnings(by["NVDA"], date(2026, 9, 10), False) is None
    assert data.next_earnings(by["NVDA"], date(2026, 9, 10), True).report_date == date(2026, 9, 12)
    # MU upcoming
    assert data.next_earnings(by["MU"], date(2026, 9, 10), True).report_date == date(2026, 9, 30)


def test_parse_portfolio_and_positions():
    p = data.parse_portfolio({"data": {"total_value": "1000", "cash": "1000",
                                       "buying_power": {"buying_power": "1000.0000"}}})
    assert p.total_value == 1000.0 and p.buying_power == 1000.0

    pos = data.parse_positions({"data": {"positions": [
        {"symbol": "NVDA", "quantity": "2.0", "average_buy_price": "176.89"},
        {"symbol": "OLD", "quantity": "0", "average_buy_price": "0"},
    ]}})
    assert set(pos) == {"NVDA"}
    assert pos["NVDA"].quantity == 2.0


def test_parse_quotes_and_closes():
    resp = json.loads((FIX / "quotes_4syms.json").read_text())
    q = data.parse_quotes(resp)
    assert q["NVDA"] == pytest.approx(218.15)
    assert set(q) == {"AVGO", "NVDA", "MU", "QQQ"}
    c = data.official_closes(resp)
    assert c["MU"] == pytest.approx(1027.77)


def test_parse_quotes_skips_inactive():
    resp = {"data": {"results": [
        {"quote": {"symbol": "AAA", "last_trade_price": "10", "state": "active", "has_traded": True}},
        {"quote": {"symbol": "BBB", "last_trade_price": "20", "state": "halted", "has_traded": True}},
        {"quote": {"symbol": "CCC", "last_trade_price": "30", "state": "active", "has_traded": False}},
    ]}}
    assert data.parse_quotes(resp) == {"AAA": 10.0}


def test_count_todays_fills():
    resp = {"data": {"orders": [
        {"created_at": "2026-09-10T14:00:00Z", "state": "filled"},
        {"created_at": "2026-09-10T15:00:00Z", "state": "cancelled"},
        {"last_transaction_at": "2026-09-09T15:00:00Z", "state": "filled"},
        {"created_at": "2026-09-10T16:00:00Z", "state": "partially_filled"},
    ]}}
    assert data.count_todays_fills(resp, date(2026, 9, 10)) == 2
