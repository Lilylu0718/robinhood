你是 robinhood-bot 的每日执行器。当前目录是项目根。按下面步骤做，不要跳步，不要即兴发挥。

## 0. 前置
- 读 `CLAUDE.md` 和 `config.py`。确认 `DRY_RUN`。
- 确认 venv：`venv/bin/python3 -c "import pandas"`，报错就 `venv/bin/pip install -q -r requirements.txt`。
- 今天日期（美东）：`TZ=America/New_York date +%F`，记为 TODAY。

## 1. 取数（全部用 robinhood-trading MCP，逐个 try；失败的那项写空文件 `{}` 并继续）
把每个返回的完整 JSON 写到项目根的文件里：
- `get_accounts` → 先确认恰好一个账户 `agentic_allowed=true` 且它的 `account_number` == `config.ACCOUNT_NUMBER`（414480244）。**不一致就停，什么都不做，报告异常。**
- `get_equity_historicals`（symbols=AVGO,NVDA,MU,QQQ；interval=day；start_time = TODAY 往前 100 天）→ `_hist.json`
- `get_earnings_calendar`（start_date=TODAY，days=31）→ `_earn.json`
- `get_equity_quotes`（AVGO,NVDA,MU,QQQ）→ `_quotes.json`
- `get_portfolio`（414480244）→ `_portfolio.json`
- `get_equity_positions`（414480244）→ `_positions.json`
- `get_equity_orders`（414480244，created_at_gte=TODAY）→ `_orders.json`

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
