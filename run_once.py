"""一次运行的确定性入口。

Claude 会话把 7 个 MCP 返回写成 JSON 文件，然后：
  venv/bin/python3 run_once.py --historicals h.json --earnings e.json \
      --quotes q.json --portfolio p.json --positions pos.json --orders o.json \
      --today 2026-09-11

daily_pnl_pct 从 equity.csv 最后一行的 total_value 推算（没有则 0）。
跑完写 last_run.md（给通知用）+ 打印摘要。有 errors 或产生了 order_plans 时退出码非 0。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import config
import logger
import main
from data import parse_portfolio, parse_positions

ROOT = Path(__file__).parent


def _load(p: str | None):
    if not p:
        return None
    try:
        return json.loads(Path(p).read_text())
    except Exception as e:  # noqa: BLE001
        print(f"WARN 读取 {p} 失败: {e}", file=sys.stderr)
        return None


def _prev_total_value() -> float | None:
    f = ROOT / config.EQUITY_CSV
    if not f.exists():
        return None
    rows = list(csv.DictReader(f.open()))
    if not rows:
        return None
    try:
        return float(rows[-1]["total_value"])
    except (KeyError, ValueError):
        return None


def main_cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--historicals")
    ap.add_argument("--earnings")
    ap.add_argument("--quotes")
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--positions", required=True)
    ap.add_argument("--orders")
    ap.add_argument("--today", required=True)
    a = ap.parse_args()

    today = date.fromisoformat(a.today)
    portfolio_resp = _load(a.portfolio)
    positions_resp = _load(a.positions)
    if portfolio_resp is None or positions_resp is None:
        print("FATAL: 缺组合/持仓数据，中止（不下任何单）")
        return 2

    portfolio = parse_portfolio(portfolio_resp)
    prev = _prev_total_value()
    daily_pnl_pct = 0.0 if not prev else (portfolio.total_value / prev - 1.0)

    res = main.run_pipeline(
        historicals_resp=_load(a.historicals),
        earnings_resp=_load(a.earnings),
        quotes_resp=_load(a.quotes),
        portfolio_resp=portfolio_resp,
        positions_resp=positions_resp,
        orders_resp=_load(a.orders),
        today=today,
        daily_pnl_pct=daily_pnl_pct,
    )

    positions = parse_positions(positions_resp)
    logger.log_equity(portfolio, positions)

    lines = [
        f"# robinhood-bot 运行 {a.today}",
        "",
        f"DRY_RUN={config.DRY_RUN} | 账户 {config.ACCOUNT_NUMBER} | "
        f"总值 ${portfolio.total_value:.2f} | 当日 {daily_pnl_pct:+.2%}",
        "",
    ]
    for rr in res.risk_results:
        s = rr.signal
        mark = "🔴 下单" if rr.approved else "·"
        extra = ""
        if rr.approved and rr.order_side == "buy":
            extra = f" → BUY ${rr.dollar_amount:.2f}"
        elif rr.approved and rr.order_side == "sell":
            extra = f" → SELL {rr.quantity} 股"
        lines.append(f"- {mark} **{s.symbol} {s.action}**{extra} — {s.reason}")
        if rr.approved:
            lines.append(f"    风控: {rr.reason}")
    if res.errors:
        lines += ["", "## errors", *[f"- {e}" for e in res.errors]]
    if res.order_plans:
        lines += ["", f"## ⚠️ {len(res.order_plans)} 个 order_plan（DRY_RUN 下不应出现）"]

    report = "\n".join(lines)
    (ROOT / "last_run.md").write_text(report + "\n")
    print(report)

    if res.errors:
        return 1
    if res.order_plans and config.DRY_RUN:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
