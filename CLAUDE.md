# Robinhood 自动交易实验 — 项目规则

本金 $1000（独立 Agentic 实验账户 `414480244`，昵称 "Agentic"），全自动下单，观察窗口 ≤1个月。

## 交易通道：官方 Robinhood Agentic Trading MCP
- MCP server：`https://agent.robinhood.com/mcp/trading`（2026-11-12 起用 claude.ai 连接器 "robinhood"，在 claude.ai 设置→连接器里授权；本地 robinhood-trading 已删除，因为同 URL 会挡住 claude.ai 连接器）
- 官方授权、不违反 ToS。**已弃用 `robin_stocks`**（逆向库，见 git 历史）。
- MCP 工具只在 Claude Agent 会话里可用，普通 `python xxx.py` 脚本调不到。因此本项目的"运行时"是一个按计划触发的 Claude Code 会话（见下"运行模型"），不是 headless cron 脚本。
- 三个账户里 **只有 `414480244` 的 `agentic_allowed=true`**，我只能对它下单。主账户 `624891156`、"Summer fling" `554410696` 我只读、永不下单。

## 当前状态（每次推进阶段后手动更新这两行）
- 阶段：E 真钱交易。**2026-11-12 起在 Anthropic 云端运行**（不再依赖 Mac）：routine `robinhood-bot hourly (trade)`（trig_014vq1Txca5Z9szr595Eg9qN，cron `45 14-20 * * 1-5` UTC = 工作日 6:45–12:45 PST 每小时一次完整研判+交易）和 `robinhood-bot weekly (review+scan)`（trig_01GNT4sVd62xjyAtfqBhe3MX，周五 13:30 PST）。入口 `cloud_run.md`；云端工具前缀 `mcp__robinhood__`；ntfy 被云端网络拦截，通知走 Claude App 推送。Mac 上的 launchd 任务已全部 unload（保留脚本作备用，勿与云端同时开）。**夏令时（2027-03-14 起）cron 要改成 `45 13-19 * * 1-5` 和 `30 20 * * 5`。**
- 上线首周要盯：抄底策略未经回测；真实下单路径（review→place→record_order.py）首次被信号触发。
- `config.py` 里 DRY_RUN：False
- **例外**：1 股 PURR（Hyperliquid Strategies，成本 $13.80，2026-09-18 真单冒烟测试买入）。2026-11-02 用户决定**长期持有、不卖**，已加入 `config.LONG_TERM_HOLDS`，止损不再对它生效。

## 硬性规则（任何代码修改都不能违反）
1. 所有 MCP 工具调用（`mcp__claude_ai_robinhood__*`）必须包在 try/except 里；失败时记录日志并跳过这次交易，**禁止用旧数据或默认值强行下单**（接口随时可能变化失效）。
2. 任何 BUY/SELL 信号下单前必须先过 `risk.py` 的 `check_risk()`。
3. 下单只能针对 `config.ACCOUNT_NUMBER`（= `414480244`）。下单前先用 `get_accounts` 确认该账户 `agentic_allowed=true`；若返回的可交易账户不是 `414480244`，**中止，不下单**（防止误碰其它账户）。
4. `DRY_RUN=True` 时，`executor.py` 只能打印，不能调用 `place_equity_order` / `place_crypto_order` / `place_option_order`。
5. `DRY_RUN=False` 时，每笔真实下单前必须先调 `review_equity_order`，把预估成本和 alert 写进日志，再 `place_equity_order`（带幂等 `ref_id`）。
6. 每次信号判断（含 HOLD）都要写入 `decisions.csv`，带 `reason` 字段。
7. `.env` 不进 git。MCP 的 OAuth token 由 Claude Code 自己管理，不出现在代码/对话/日志里。本项目已不需要任何 Robinhood 账号密码。

## 风控参数（数值见 config.py，推导理由见 docs/strategy-design.md）
单标的仓位 ≤25% ｜ 止损 -15%（仅卫星）｜ 单日亏 -3% 停开卫星仓 ｜ 每日笔数不限（保险丝 10）

## 文件结构
```
config.py   # 所有可调参数（含 ACCOUNT_NUMBER、DRY_RUN、风控/策略常量）
data.py     # 纯函数：把 MCP 返回的 bars/quotes/earnings 解析成 DataFrame / 结构体
strategy.py # 纯函数：MA10/MA30 交叉 + 财报避雷，生成带 reason 的信号
risk.py     # 纯函数：仓位/止损/日亏/频率检查
executor.py # DRY_RUN 打印 vs 真实下单（真实分支由 Claude 在会话里调 MCP 完成）
logger.py   # 决策（含HOLD）写 decisions.csv、每日市值写 equity.csv
main.py     # 每日主流程编排（见"运行模型"）
```
`strategy.py` / `risk.py` / `logger.py` / `data.py` 是纯 Python、可单测。`data.py` 和 `executor.py` 不直接发 MCP 请求 —— MCP 调用由 Claude 会话完成，把结果喂给这些纯函数。

## 运行模型
每日流程（`main.py` 编排，Claude 会话执行）：
1. Claude 调 `get_equity_historicals`（4个标的）、`get_earnings_calendar`、`get_portfolio`、`get_equity_positions`、`get_equity_orders`
2. 把 bars 喂给 `data.py` → `strategy.py` 生成信号（每个带 reason）
3. 信号 + 组合状态喂给 `risk.py` → 批准/拒绝
4. `executor.py`：DRY_RUN 打印；否则 Claude 调 `review_equity_order` →（人工/自主确认）→ `place_equity_order`
5. `logger.py` 写 `decisions.csv` + `equity.csv`
调度方式（cron 触发 `claude -p` 还是别的）在阶段 E 定，见 execution-checklist.md。

## 当前策略版本（2026-11-02 起）
**核心大厂（`CORE_SYMBOLS`：GOOGL/AAPL/NVDA/AVGO/MSFT/AMZN/META）——低点买入、永不卖出、不止损。**
- 买入来源：① 机械抄底（距 20 日高回撤 ≥8% 且 RSI ≤40）；② Claude 每日研判（daily_prompt 1.7，查新闻/评级/估值，写 `_judgment.json`，只能 BUY 核心股或 SKIP 否决，不能 SELL）。
- 每次买 10% 总值，单只 ≤25%；已持有的只在比成本再低 ≥8% 时加仓。大跌日不受 -3% 日亏停开仓约束。
**卫星（`SATELLITE_SYMBOLS`：MU/QQQ）——抄底 + 止盈 +10% / 站回 MA20 且 ≥+3% 离场 + 止损 -15%。**每次建仓 20%。**MU 2026-11-05 起用户要求保留、不止损**（止盈/反弹离场仍有效）。
**2026-11-12 起 Claude 是决策者**（用户："不要死板看规则"、"完全自主"）：机械信号只是提名；`_judgment.json` 可 BUY 池内任何标的、SKIP 任何买入、SELL 已持有的卫星仓（核心/MU/PURR 永不卖）。会下单的决定先开看多/看空子 agent 对辩。
**PURR**：长期持有不卖。每日交易笔数上限已取消（保留 10 笔作防失控保险丝）。财报前 2 天不开新仓。
不把"发布会必跌"之类伪规律当信号。`docs/strategy-design.md` 是旧 MA 策略的设计讨论。

## 按需读取（不要默认加载，用到时才读）
- `docs/account-setup.md` — MCP 接入、账户确认、认证方式，仅当 MCP/账户相关出问题时读
- `docs/strategy-design.md` — 四层策略设计的完整讨论和取舍理由，仅当调整 strategy.py 逻辑时读
- `docs/execution-checklist.md` — 阶段A-E上线清单，仅当推进到新阶段时读
