"""决策与市值落盘。decisions.csv 每次信号判断（含 HOLD）一行；equity.csv 每日一行。"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

import config
from data import Portfolio, Position
from risk import RiskResult

_DECISION_FIELDS = [
    "ts_utc",
    "date",
    "symbol",
    "action",          # BUY / SELL / HOLD（来自 strategy）
    "signal_reason",
    "risk_approved",   # True / False
    "risk_reason",
    "order_side",      # buy / sell / ""
    "order_dollars",   # BUY 金额
    "order_quantity",  # SELL 股数
    "dry_run",
    "ref_id",          # 真实下单的幂等键
    "order_state",     # placed / filled / rejected / dry_run / skipped ...
    "notes",
]

_EQUITY_FIELDS = ["ts_utc", "date", "total_value", "cash", "buying_power", "positions"]


def _append(path: str, fields: list[str], row: dict) -> None:
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def log_decision(
    rr: RiskResult,
    *,
    dry_run: bool = config.DRY_RUN,
    ref_id: str = "",
    order_state: str = "",
    notes: str = "",
    path: str = config.DECISIONS_CSV,
) -> None:
    now = datetime.now(timezone.utc)
    _append(
        path,
        _DECISION_FIELDS,
        {
            "ts_utc": now.isoformat(timespec="seconds"),
            "date": now.date().isoformat(),
            "symbol": rr.signal.symbol,
            "action": rr.signal.action,
            "signal_reason": rr.signal.reason,
            "risk_approved": rr.approved,
            "risk_reason": rr.reason,
            "order_side": rr.order_side or "",
            "order_dollars": "" if rr.dollar_amount is None else f"{rr.dollar_amount:.2f}",
            "order_quantity": "" if rr.quantity is None else f"{rr.quantity}",
            "dry_run": dry_run,
            "ref_id": ref_id,
            "order_state": order_state,
            "notes": notes,
        },
    )


def log_equity(
    portfolio: Portfolio,
    positions: dict[str, Position],
    *,
    path: str = config.EQUITY_CSV,
) -> None:
    now = datetime.now(timezone.utc)
    _append(
        path,
        _EQUITY_FIELDS,
        {
            "ts_utc": now.isoformat(timespec="seconds"),
            "date": now.date().isoformat(),
            "total_value": f"{portfolio.total_value:.2f}",
            "cash": f"{portfolio.cash:.2f}",
            "buying_power": f"{portfolio.buying_power:.2f}",
            "positions": json.dumps(
                {s: {"qty": p.quantity, "avg": p.average_buy_price} for s, p in positions.items()},
                ensure_ascii=False,
            ),
        },
    )
