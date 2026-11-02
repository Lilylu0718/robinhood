"""真实下单后把结果补记到 decisions.csv（和 run_once 写的 planned 行用 ref_id 关联）。

venv/bin/python3 record_order.py --ref-id <uuid> --symbol NVDA --side buy \
    --state placed|filled|rejected|failed|review_blocked --notes "review 预估 $200.00; alerts: ...; order_id ..."
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone

import config
from logger import _DECISION_FIELDS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-id", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--side", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    new = not os.path.exists(config.DECISIONS_CSV)
    with open(config.DECISIONS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_DECISION_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: "" for k in _DECISION_FIELDS} | {
            "ts_utc": now.isoformat(timespec="seconds"),
            "date": now.date().isoformat(),
            "symbol": a.symbol,
            "action": a.side.upper(),
            "signal_reason": "下单结果回填",
            "order_side": a.side,
            "dry_run": False,
            "ref_id": a.ref_id,
            "order_state": a.state,
            "notes": a.notes,
        })
    print(f"recorded {a.symbol} {a.side} {a.state} ref={a.ref_id}")


if __name__ == "__main__":
    main()
