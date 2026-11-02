你是 robinhood-bot 的每日执行器。当前目录是项目根。按下面步骤做，不要跳步，不要即兴发挥。

## 0. 前置
- 读 `CLAUDE.md` 和 `config.py`。确认 `DRY_RUN`。
- 确认 venv：`venv/bin/python3 -c "import pandas"`，报错就 `venv/bin/pip install -q -r requirements.txt`。
- 今天日期（美东）：`TZ=America/New_York date +%F`，记为 TODAY。

## 1. 取数（全部用 robinhood-trading MCP，逐个 try；失败的那项写空文件 `{}` 并继续）
**连接性重试**：任何一次 MCP 调用失败（DNS 解析失败、socket 被关、超时等连接类错误——不是"账户不对"这种业务错误），
先等 20 秒重试，最多重试 2 次（合计最多 3 次尝试）。3 次都失败才算这项"拉取失败"。
`get_accounts` 这步尤其要走满重试再放弃——它是后续账户安全校验的前提。
把每个返回的完整 JSON 写到项目根的文件里：
- `get_accounts` → 先确认恰好一个账户 `agentic_allowed=true` 且它的 `account_number` == `config.ACCOUNT_NUMBER`（414480244）。**不一致就停，什么都不做，报告异常。**
- `get_equity_historicals`（symbols=AVGO,NVDA,MU,QQQ,GOOGL,AAPL；interval=day；start_time = TODAY 往前 100 天）→ `_hist.json`
- `get_earnings_calendar`（start_date=TODAY，days=31）→ `_earn.json`
- `get_equity_quotes`（AVGO,NVDA,MU,QQQ,GOOGL,AAPL）→ `_quotes.json`
- `get_portfolio`（414480244）→ `_portfolio.json`
- `get_equity_positions`（414480244）→ `_positions.json`
- `get_equity_orders`（414480244，created_at_gte=TODAY）→ `_orders.json`

## 1.5 长期持有仓位（PURR，只读汇报，永不卖出）
1股 PURR（Hyperliquid Strategies），成本 $13.80。2026-11-02 用户决定长期持有：`config.LONG_TERM_HOLDS` 已把它排除在止损之外，bot 不会对它生成任何 SELL。
每次跑到这一步：`get_equity_quotes`（PURR）拿现价，在 `last_run.md` 里加一行"PURR 长期持有：现价、盈亏%"，不标止损/止盈建议。不用写 decisions.csv。

## 2. 跑流程
```
venv/bin/python3 run_once.py --historicals _hist.json --earnings _earn.json \
  --quotes _quotes.json --portfolio _portfolio.json --positions _positions.json \
  --orders _orders.json --today <TODAY>
```
它会写 `decisions.csv` / `equity.csv` / `last_run.md`。

## 3. 下单分支
- `config.DRY_RUN` 为 True：到此为止，**绝不下单**。
- `config.DRY_RUN` 为 False（2026-11-02 起）：如果 `_order_plans.json` 存在，对其中**每一笔**按顺序做：
  1. 再确认：`account_number` == `414480244`，且第 1 步 `get_accounts` 校验已通过。不满足 → 全部跳过，报告异常。
  2. `review_equity_order`，参数用 plan 里的字段（account_number / symbol / side / type / dollar_amount 或 quantity / market_hours）。
     失败（走 1 节的连接重试后仍失败）或返回阻断性 alert → 不下单，
     `venv/bin/python3 record_order.py --ref-id <ref_id> --symbol <S> --side <side> --state review_blocked --notes "<原因>"`，继续下一笔。
  3. 把 review 的预估成本 + alerts 记下来，然后 `place_equity_order(**plan)`（**必须带 plan 里的 ref_id**，幂等；重试也用同一个 ref_id）。
  4. `record_order.py --ref-id ... --state <返回的订单状态> --notes "预估 $X; alerts: ...; order_id ..."`。
     place 失败也要 record（state=failed + 错误信息），**不要换参数硬下**。
  5. 在 `last_run.md` 末尾追加一行这笔单的结果（✅ 已下单 / ❌ 失败 + 原因）。
  - review 返回 `customer_approval_required=true` 且无 order_checks alert：照常 place（订单会推到用户 Robinhood app 等批准），state 记 `awaiting_approval`，last_run.md 标「📱 待你在 app 批准」。
  - 绝不下 plan 之外的单，绝不改金额/方向/标的。`_order_plans.json` 不存在 = 今天不交易。
  - `run_once.py` 退出码非 0 且有 errors 时：不执行任何 plan，报告里标红。

## 4. 收尾
- 删除 `_*.json` 临时文件（含 `_order_plans.json`，下完单后）。
- `git add decisions.csv equity.csv last_run.md && git commit -m "run <TODAY>" && git push`（推失败不算致命，继续）。
- 最后输出一段**不超过 6 行**的中文摘要：每个标的的决策 + 有没有下单 + 有没有 error。这段会进桌面/手机通知。
