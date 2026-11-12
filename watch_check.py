"""盯盘：算盘中涨跌幅，挑出值得追加完整运行的异动标的。纯本地计算，不碰 MCP。

用法：venv/bin/python3 watch_check.py --quotes _watch_quotes.json --today 2026-11-12
输入是 get_equity_quotes 的原始返回（data.results[].quote / .close）。
状态存 research/watch_state.json：同一标的同一天只在涨跌幅比上次触发再扩大 ≥2 个点时再报，避免每 30 分钟重复触发。
买入区间：research/buy_zones.json（每周复盘/研判维护）{"NVDA": {"buy_below": 150, "paused": false, "note": "..."}}。
现价 ≤ buy_below 且未 paused → 输出 ZONE 行（同日只在比上次再低 2% 时重复）。
输出每行一个候选：MOVE <SYM> <+/-x.x%> <price> <prev_close> / ZONE <SYM> <price> <= <buy_below>；都没有输出 NO_MOVES。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import data

MOVE_PCT = 0.04          # 盘中涨跌 ≥4% 视为异动
RETRIGGER_STEP = 0.02    # 同日再触发需比上次再扩大 2 个点
STATE = Path(__file__).parent / "research" / "watch_state.json"
ZONES = Path(__file__).parent / "research" / "buy_zones.json"


def find_moves(prices: dict[str, float], closes: dict[str, float], state: dict, today: str):
    if state.get("date") != today:
        state.clear()
        state.update({"date": today, "triggered": {}})
    trig = state["triggered"]
    out = []
    for sym, px in prices.items():
        prev = closes.get(sym)
        if not prev:
            continue
        chg = px / prev - 1
        if abs(chg) < MOVE_PCT:
            continue
        last = trig.get(sym)
        if last is not None and abs(chg) < abs(last) + RETRIGGER_STEP and (chg > 0) == (last > 0):
            continue
        trig[sym] = round(chg, 4)
        out.append((sym, chg, px, prev))
    return out


def find_zone_hits(prices: dict[str, float], zones: dict, state: dict):
    """在 find_moves 之后调用（state 已按日期重置）。"""
    hit = state.setdefault("zones", {})
    out = []
    for sym, z in zones.items():
        try:
            below, paused = float(z["buy_below"]), bool(z.get("paused", False))
        except Exception:  # noqa: BLE001
            continue
        px = prices.get(sym)
        if paused or px is None or px > below:
            continue
        last = hit.get(sym)
        if last is not None and px > last * (1 - RETRIGGER_STEP):
            continue
        hit[sym] = px
        out.append((sym, px, below))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quotes", required=True)
    ap.add_argument("--today", required=True)
    a = ap.parse_args()
    resp = json.loads(Path(a.quotes).read_text())
    prices, closes = data.parse_quotes(resp), data.official_closes(resp)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    moves = find_moves(prices, closes, state, a.today)
    try:
        zones = json.loads(ZONES.read_text()) if ZONES.exists() else {}
    except Exception:  # noqa: BLE001
        zones = {}
    zone_hits = find_zone_hits(prices, zones, state)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))
    for sym, chg, px, prev in moves:
        tag = " (core)" if sym in config.CORE_SYMBOLS else ""
        print(f"MOVE {sym} {chg:+.1%} {px:.2f} {prev:.2f}{tag}")
    for sym, px, below in zone_hits:
        print(f"ZONE {sym} {px:.2f} <= {below:.2f}")
    if not moves and not zone_hits:
        print("NO_MOVES")


if __name__ == "__main__":
    main()
