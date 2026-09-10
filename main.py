"""每日主流程编排。

MCP 调用不在这里——由 Claude 在会话里完成，把 response dict 传进 run_pipeline()。

═══ 每日 RUNBOOK（Claude 按此执行）═══
1. 取数（MCP，全部 try/except，失败则该项传 None）：
   - get_equity_historicals(SYMBOLS, start=今天-HIST_LOOKBACK_DAYS, interval="day")
   - get_earnings_calendar(start_date=今天, days=31)
   - get_equity_quotes(SYMBOLS)
   - get_portfolio(ACCOUNT_NUMBER)
   - get_equity_positions(ACCOUNT_NUMBER)
   - get_equity_orders(ACCOUNT_NUMBER, created_at_gte=今天0点UTC)
2. daily_pnl_pct：用 get_portfolio 的 total_value 和 equity.csv 里昨天的收盘市值算；
   equity.csv 为空则传 0.0。
3. 调 run_pipeline(...)。它跑 stop-loss → MA 信号 → 风控 → executor，
   写 decisions.csv，返回 PipelineResult。
4. DRY_RUN=True：到此为止，看 result.order_plans 应为空、result.printed 是打印内容。
   DRY_RUN=False：对 result.order_plans 里每个 plan：
     a. assert_account_safe(plan.account_number)（已在 build 时做过，再确认一次）
     b. review_equity_order(**plan.as_mcp_kwargs() 去掉 ref_id 之外可保留)
     c. 人工/自主确认 → place_equity_order(**plan.as_mcp_kwargs())
     d. logger.log_decision(..., ref_id=plan.ref_id, order_state=返回状态)
5. logger.log_equity(portfolio, positions) 收尾。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import config
import data
import executor
import logger
from risk import RiskContext, check_risk, stop_loss_signals
from strategy import Signal, generate_signals


@dataclass
class PipelineResult:
    signals: list[Signal] = field(default_factory=list)
    risk_results: list = field(default_factory=list)
    order_plans: list[executor.OrderPlan] = field(default_factory=list)
    printed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _safe(fn, label, errors):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        errors.append(f"{label}: {type(e).__name__}: {e}")
        return None


def run_pipeline(
    *,
    historicals_resp: dict | None,
    earnings_resp: dict | None,
    quotes_resp: dict | None,
    portfolio_resp: dict | None,
    positions_resp: dict | None,
    orders_resp: dict | None,
    today: date,
    daily_pnl_pct: float,
    dry_run: bool = config.DRY_RUN,
) -> PipelineResult:
    res = PipelineResult()

    if portfolio_resp is None or positions_resp is None:
        res.errors.append("缺组合/持仓数据，中止本次运行（不下任何单）")
        return res

    portfolio = data.parse_portfolio(portfolio_resp)
    positions = data.parse_positions(positions_resp)
    quotes = data.parse_quotes(quotes_resp) if quotes_resp else {}
    dfs = _safe(lambda: data.parse_historicals(historicals_resp), "parse_historicals", res.errors) or {}
    earnings = (
        _safe(lambda: data.parse_earnings_calendar(earnings_resp, config.SYMBOLS),
              "parse_earnings", res.errors)
        or {s: [] for s in config.SYMBOLS}
    )
    todays_fills = (
        _safe(lambda: data.count_todays_fills(orders_resp, today), "count_fills", res.errors)
        if orders_resp else 0
    ) or 0

    ctx = RiskContext(
        portfolio=portfolio,
        positions=positions,
        quotes=quotes,
        todays_fills=todays_fills,
        daily_pnl_pct=daily_pnl_pct,
        today=today,
    )

    # 1) 止损信号优先，且同一标的止损后不再处理 MA 信号
    stop_signals = stop_loss_signals(ctx)
    stopped = {s.symbol for s in stop_signals}

    # 2) MA 信号（离场按"持仓 + 空头排列"，入场按"新金叉"）
    held = set(positions) - stopped
    ma_signals = [
        s for s in generate_signals(dfs, earnings, today, held_symbols=held)
        if s.symbol not in stopped
    ]

    res.signals = stop_signals + ma_signals

    for sig in res.signals:
        rr = check_risk(sig, ctx)
        res.risk_results.append(rr)
        state, payload = executor.execute(rr, dry_run=dry_run)
        if state == "dry_run":
            res.printed.append(payload)
            logger.log_decision(rr, dry_run=True, order_state="dry_run")
        elif state == "skipped":
            logger.log_decision(rr, dry_run=dry_run, order_state="skipped")
        elif state == "needs_mcp":
            res.order_plans.append(payload)
            # 先落一条 planned 行；Claude 走完 review→place 后再落一条结果行
            logger.log_decision(rr, dry_run=False, ref_id=payload.ref_id,
                                order_state="planned")

    return res
