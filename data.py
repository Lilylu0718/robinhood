"""纯函数：把 MCP 工具的返回 JSON 解析成干净的结构。

这里**不发任何 MCP 请求**。MCP 调用由 Claude 在会话里完成，把 response dict 传进来。
每个函数接受的是 MCP 工具返回的完整 dict（形如 {"data": {...}, "guide": "..."}）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


# ── 价格数据 ─────────────────────────────────────────────────────────
def parse_historicals(resp: dict) -> dict[str, pd.DataFrame]:
    """get_equity_historicals 的返回 → {symbol: DataFrame}。

    DataFrame: index 为 date（升序），列 open/high/low/close/volume（float）。
    interpolated=true 的 bar 丢弃（gap-fill，无信息）。
    """
    out: dict[str, pd.DataFrame] = {}
    for r in resp["data"]["results"]:
        rows = []
        for b in r["bars"]:
            if b.get("interpolated"):
                continue
            rows.append(
                {
                    "date": datetime.fromisoformat(
                        b["begins_at"].replace("Z", "+00:00")
                    ).date(),
                    "open": float(b["open_price"]),
                    "high": float(b["high_price"]),
                    "low": float(b["low_price"]),
                    "close": float(b["close_price"]),
                    "volume": int(b["volume"]),
                }
            )
        df = pd.DataFrame(rows).set_index("date").sort_index()
        out[r["symbol"]] = df
    return out


def parse_quotes(resp: dict) -> dict[str, float]:
    """get_equity_quotes 的返回 → {symbol: 现价(float)}。

    形状：data.results[] = [{"quote": {...}, "close": {...}}, ...]
    现价取 quote.last_trade_price（回退 last_non_reg_trade_price）。
    state != "active" 或 has_traded=false 的跳过（调用方拿不到价格自然不下单）。
    """
    out: dict[str, float] = {}
    for r in resp["data"]["results"]:
        q = r.get("quote") or {}
        if q.get("state") not in (None, "active") or q.get("has_traded") is False:
            continue
        price = q.get("last_trade_price") or q.get("last_non_reg_trade_price")
        if price is not None:
            out[q["symbol"]] = float(price)
    return out


def official_closes(resp: dict) -> dict[str, float]:
    """get_equity_quotes 的返回 → {symbol: 官方结算收盘价(float)}（data.results[].close）。"""
    out: dict[str, float] = {}
    for r in resp["data"]["results"]:
        c = r.get("close") or {}
        if c.get("price") is not None:
            out[c["symbol"]] = float(c["price"])
    return out


# ── 财报日历 ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EarningsEvent:
    symbol: str
    report_date: date
    timing: str | None      # "am" / "pm" / None
    verified: bool
    reported: bool          # eps.actual 非空 = 已公布


def parse_earnings_calendar(resp: dict, symbols: tuple[str, ...]) -> dict[str, list[EarningsEvent]]:
    """get_earnings_calendar 的返回 → {symbol: [EarningsEvent, ...]}（只保留 symbols 里的）。

    返回按 report_date 升序；已公布(reported=True)的也保留，调用方自己按需过滤。
    """
    want = {s.upper() for s in symbols}
    out: dict[str, list[EarningsEvent]] = {s: [] for s in symbols}
    for e in resp["data"]["results"]:
        sym = e["symbol"].upper()
        if sym not in want:
            continue
        rep = e["report"]
        out[sym].append(
            EarningsEvent(
                symbol=sym,
                report_date=date.fromisoformat(rep["date"]),
                timing=rep.get("timing"),
                verified=bool(rep.get("verified")),
                reported=(e.get("eps", {}) or {}).get("actual") is not None,
            )
        )
    for s in out:
        out[s].sort(key=lambda ev: ev.report_date)
    return out


def next_earnings(
    events: list[EarningsEvent], on: date, treat_tentative_as_real: bool
) -> EarningsEvent | None:
    """在 events 里找 on 当天或之后、尚未公布的下一场财报。"""
    for ev in events:
        if ev.reported or ev.report_date < on:
            continue
        if not ev.verified and not treat_tentative_as_real:
            continue
        return ev
    return None


# ── 组合 / 持仓 ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Portfolio:
    total_value: float
    cash: float
    buying_power: float


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    average_buy_price: float


def parse_portfolio(resp: dict) -> Portfolio:
    d = resp["data"]
    return Portfolio(
        total_value=float(d["total_value"]),
        cash=float(d["cash"]),
        buying_power=float(d["buying_power"]["buying_power"]),
    )


def parse_positions(resp: dict) -> dict[str, Position]:
    out: dict[str, Position] = {}
    for p in resp["data"]["positions"]:
        qty = float(p["quantity"])
        if qty == 0:
            continue
        out[p["symbol"]] = Position(
            symbol=p["symbol"],
            quantity=qty,
            average_buy_price=float(p.get("average_buy_price") or 0.0),
        )
    return out


def count_todays_fills(orders_resp: dict, today: date) -> int:
    """get_equity_orders 的返回里，今天 created 且已成交/部分成交的订单数。"""
    n = 0
    for o in orders_resp["data"]["orders"]:
        ts = o.get("last_transaction_at") or o.get("created_at")
        if not ts:
            continue
        d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
        if d == today and o.get("state") in ("filled", "partially_filled"):
            n += 1
    return n
