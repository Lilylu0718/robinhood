你是 robinhood-bot 的**盯盘**任务（每 15 分钟一次，只读，绝不下单）。工作目录 /Users/lilylu/robinhood-bot。目标 1-2 分钟内结束。
交易只在完整运行（daily_prompt.md）里做；你的工作是判断**要不要现在追加一次完整运行**。

1. `date` 取 TODAY（YYYY-MM-DD）和当前 PT 时间。
2. 用 Robinhood 连接器的 `get_equity_quotes`（本机前缀 `mcp__claude_ai_robinhood__`，云端前缀 `mcp__robinhood__`），symbols = `config.SYMBOLS` + `PURR`
   （用 `venv/bin/python3 -c 'import config;print(",".join(config.SYMBOLS))'` 取，池子每周会变）。原样写入 `_watch_quotes.json`。失败重试一次，仍失败 → 输出 `WATCH_TRIGGER: no (quotes failed)` 结束。
3. `venv/bin/python3 watch_check.py --quotes _watch_quotes.json --today <TODAY>` → 得到异动候选（MOVE 行）和买入区间命中（ZONE 行：价格跌进了投资档案预设的买入区间）。
4. 读 `research/buy_zones.json`、`research/views.md`（跨天持续判断，含各标的的"解除条件"）和 `research/<TODAY>.md`（今天已有的研判，可能不存在）。
5. 新闻快查（`WebSearch`，standard 模式，总共最多 3 次）：只查 ①MOVE 候选里今天笔记还没解释过原因的；②`views.md` 里正在等待解除条件的标的（每个 1 次，看有没有新进展：财报、CEO 任命、调查结论等）。
6. 判断是否触发完整运行。触发条件（任一）：
   - 有 MOVE 候选，且原因今天还没研判过（或有新原因）；
   - `views.md` 里某个解除条件**可能已满足**，或出现足以改变判断的重大新消息（正面或负面）；
   - 有 ZONE 命中（价格进入预设买入区间），且没有新的公司自身负面消息——这正是提前设好的买点，**默认触发**；
   - 核心股出现明显错杀式大跌（宏观/情绪导致，公司本身没变）——这是抄底机会，宁可多触发。
   不触发：涨跌都在已知原因范围内、views 无变化、只是正常波动。
7. 如果触发：把触发原因（标的、涨跌幅、新闻要点、时间）**追加**到 `research/<TODAY>.md` 的 "## 盯盘 HH:MM" 小节，方便完整运行直接用。
8. 最后一行**必须**是以下之一（脚本靠它判断）：
   `WATCH_TRIGGER: yes <一句话原因>`
   `WATCH_TRIGGER: no <一句话原因>`

禁止：调用任何 review/place/cancel 下单工具；修改 decisions.csv / equity.csv / last_run.md / config.py；git commit。
如果 robinhood 工具提示需要认证/授权，单独打印一行 `RH_MCP_AUTH_EXPIRED`，然后 `WATCH_TRIGGER: no (auth)`。
