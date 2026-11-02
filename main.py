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
3. 调 run_pipeline(...)。它跑 stop-loss → 抄底信号 → 风控 → executor，
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

from dataclasses import dataclass, field, replace
from datetime import date

import pandas as pd

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


def apply_judgments(signals: list[Signal], judgments: list[dict], errors: list[str]) -> list[Signal]:
    """Claude 研判覆盖层。只允许两种动作：
    - BUY：仅限 config.CORE_SYMBOLS，把该标的的 HOLD 改成 BUY（reason 以"判断:"开头，优先级最高）
    - SKIP：把任何标的的 BUY 否决成 HOLD
    永远不能产生 SELL。之后仍然过 check_risk。
    """
    by_sym = {s.symbol: s for s in signals}
    for j in judgments:
        try:
            sym, act, why = str(j["symbol"]).upper(), str(j["action"]).upper(), str(j["reason"]).strip()
        except Exception as e:  # noqa: BLE001
            errors.append(f"judgment 格式错误: {j!r} ({e})")
            continue
        cur = by_sym.get(sym)
        if cur is None or not why:
            errors.append(f"judgment 忽略（不在标的池或无理由）: {j!r}")
            continue
        if act == "BUY":
            if sym not in config.CORE_SYMBOLS:
                errors.append(f"judgment BUY 仅限核心大厂，忽略 {sym}")
                continue
            if cur.action == "HOLD":
                by_sym[sym] = Signal(sym, "BUY", f"判断: {why} | 原: {cur.reason}",
                                     cur.fast_ma, cur.slow_ma, score=-1.0)
        elif act == "SKIP":
            if cur.action == "BUY":
                by_sym[sym] = Signal(sym, "HOLD", f"判断否决买入: {why} | 原: {cur.reason}",
                                     cur.fast_ma, cur.slow_ma)
        else:
            errors.append(f"judgment 动作只能 BUY/SKIP，忽略 {j!r}")
    return [by_sym[s.symbol] for s in signals]


def with_live_bar(dfs: dict, quotes: dict[str, float], today: date) -> dict:
    """盘中运行：日线最后一根是昨天时，用实时价当作今天的临时收盘补一根，
    让一天多次运行都基于最新价格算回撤/RSI/MA。"""
    out = {}
    for sym, df in dfs.items():
        px = quotes.get(sym)
        if px and len(df) and df.index[-1] < today:
            row = pd.DataFrame({"open": [px], "high": [px], "low": [px], "close": [px], "volume": [0]},
                               index=[today])
            df = pd.concat([df, row])
        out[sym] = df
    return out


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
    judgments: list[dict] | None = None,
) -> PipelineResult:
    res = PipelineResult()

    if portfolio_resp is None or positions_resp is None:
        res.errors.append("缺组合/持仓数据，中止本次运行（不下任何单）")
        return res

    portfolio = data.parse_portfolio(portfolio_resp)
    positions = data.parse_positions(positions_resp)
    quotes = data.parse_quotes(quotes_resp) if quotes_resp else {}
    dfs = _safe(lambda: data.parse_historicals(historicals_resp), "parse_historicals", res.errors) or {}
    dfs = with_live_bar(dfs, quotes, today)
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

    # 2) 抄底策略信号（持仓按止盈/反弹离场，未持仓按回撤+RSI 入场）
    held = set(positions) - stopped
    avg_costs = {k: p.average_buy_price for k, p in positions.items()}
    strat_signals = [
        s for s in generate_signals(dfs, earnings, today, held_symbols=held,
                                    avg_costs=avg_costs, quotes=quotes)
        if s.symbol not in stopped
    ]
    strat_signals = apply_judgments(strat_signals, judgments or [], res.errors)
    # 卖在前（释放额度），BUY 按 score（RSI）从低到高——最超卖的优先吃掉每日交易额度
    order = {"SELL": 0, "BUY": 1, "HOLD": 2}
    strat_signals.sort(key=lambda s: (order.get(s.action, 3),
                                      s.score if s.score is not None else 999))

    res.signals = stop_signals + strat_signals

    for sig in res.signals:
        rr = check_risk(sig, ctx)
        res.risk_results.append(rr)
        if rr.approved:
            # 本次运行内已批准的单也占用当日交易次数 / 购买力
            bp = ctx.portfolio.buying_power - (rr.dollar_amount or 0.0)
            ctx = replace(ctx, todays_fills=ctx.todays_fills + 1,
                          portfolio=replace(ctx.portfolio, buying_power=bp))
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
