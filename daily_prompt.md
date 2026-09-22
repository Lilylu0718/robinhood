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
- `get_equity_historicals`（symbols=AVGO,NVDA,MU,QQQ；interval=day；start_time = TODAY 往前 100 天）→ `_hist.json`
- `get_earnings_calendar`（start_date=TODAY，days=31）→ `_earn.json`
- `get_equity_quotes`（AVGO,NVDA,MU,QQQ）→ `_quotes.json`
- `get_portfolio`（414480244）→ `_portfolio.json`
- `get_equity_positions`（414480244）→ `_positions.json`
- `get_equity_orders`（414480244，created_at_gte=TODAY）→ `_orders.json`

## 1.5 手动测试仓位监控（PURR，只读，不进 strategy.py/风控管道）
2026-09-18 一次性真单冒烟测试留下的仓位：1股 PURR，成本 $13.80（ref_id b7533b9c-7c4b-45ec-b13d-c8d9bbe85495）。
它不在 `config.SYMBOLS` 里，`generate_signals` 不会给它 MA 信号；但 `risk.stop_loss_signals` 是遍历所有持仓的，
所以 -6% 止损**会**被自动检测到——只是 `DRY_RUN=True` 时 executor 只打印不会真的卖，等于没有保护。
每次跑到这一步：
- `get_equity_quotes`（PURR）拿现价，算 `pnl_pct = 现价/13.80 - 1`
- 用 `risk.check_risk(Signal("PURR","HOLD", f"手动测试仓位监控: 现价{px} 成本13.80 盈亏{pnl_pct:+.1%}"), ctx)` 的结果调
  `logger.log_decision(...)` 落一行到 decisions.csv（不影响 MA 标的池的信号）
- 在 `last_run.md` 里加一行：现价、盈亏%
  - `pnl_pct >= 0.05`：标 🎯 已达止盈线(+5%)，建议卖出——需要人工把 `place_equity_order` 从 `.claude/settings.json` 的 `deny` 移出，Claude 才能下单
  - `pnl_pct <= -0.06`：标 ⚠️ 已达止损线(-6%)，DRY_RUN 下不会自动卖，同样需要人工解锁 `place_equity_order`
  - 否则不用特别标注，正常报数字即可
卖出后把这一节从 daily_prompt.md 删掉（仓位已清，不用再监控）。

## 2. 跑流程
```
venv/bin/python3 run_once.py --historicals _hist.json --earnings _earn.json \
  --quotes _quotes.json --portfolio _portfolio.json --positions _positions.json \
  --orders _orders.json --today <TODAY>
```
它会写 `decisions.csv` / `equity.csv` / `last_run.md`。

## 3. DRY_RUN 分支
- `config.DRY_RUN` 为 True（现阶段）：到此为止。`run_once.py` 退出码非 0 就在报告里标红。**绝不下单**（下单工具已被 deny）。
- 将来 `DRY_RUN=False` 时：本 prompt 需要更新，加 review→（人工/自主确认）→ place 的步骤。现在不用管。

## 4. 收尾
- 删除 `_*.json` 临时文件。
- `git add decisions.csv equity.csv last_run.md && git commit -m "run <TODAY>" && git push`（推失败不算致命，继续）。
- 最后输出一段**不超过 6 行**的中文摘要：每个标的的决策 + 有没有下单 + 有没有 error。这段会进桌面/手机通知。
