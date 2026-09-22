# Robinhood 自动交易实验 — 项目规则

本金 $1000（独立 Agentic 实验账户 `414480244`，昵称 "Agentic"），全自动下单，观察窗口 ≤1个月。

## 交易通道：官方 Robinhood Agentic Trading MCP
- MCP server：`https://agent.robinhood.com/mcp/trading`（`claude mcp add robinhood-trading ...`，`/mcp` 认证）
- 官方授权、不违反 ToS。**已弃用 `robin_stocks`**（逆向库，见 git 历史）。
- MCP 工具只在 Claude Agent 会话里可用，普通 `python xxx.py` 脚本调不到。因此本项目的"运行时"是一个按计划触发的 Claude Code 会话（见下"运行模型"），不是 headless cron 脚本。
- 三个账户里 **只有 `414480244` 的 `agentic_allowed=true`**，我只能对它下单。主账户 `624891156`、"Summer fling" `554410696` 我只读、永不下单。

## 当前状态（每次推进阶段后手动更新这两行）
- 阶段：D 进行中（纸面验证，DRY_RUN=True）。launchd `com.lilylu.robinhood-bot` 已装，工作日 10:00 + 13:15 PT 自动跑。见 decisions.csv / last_run.md。
- `config.py` 里 DRY_RUN：True
- **例外**：2026-09-18 手动做过一次真单冒烟测试（用户明确授权，验证 review→place 全链路），持有 1 股 PURR，成本 $13.80，不在 `config.SYMBOLS` 策略池内。止盈 +5%/止损 -6% 阈值监控见 `daily_prompt.md` 1.5 节；DRY_RUN=True 下止损信号只打印不会真卖，触发时需人工把 `place_equity_order` 从 `.claude/settings.json` 的 `deny` 移出才能下单。卖出后删掉这条和 daily_prompt.md 对应小节。

## 硬性规则（任何代码修改都不能违反）
1. 所有 MCP 工具调用（`mcp__robinhood-trading__*`）必须包在 try/except 里；失败时记录日志并跳过这次交易，**禁止用旧数据或默认值强行下单**（接口随时可能变化失效）。
2. 任何 BUY/SELL 信号下单前必须先过 `risk.py` 的 `check_risk()`。
3. 下单只能针对 `config.ACCOUNT_NUMBER`（= `414480244`）。下单前先用 `get_accounts` 确认该账户 `agentic_allowed=true`；若返回的可交易账户不是 `414480244`，**中止，不下单**（防止误碰其它账户）。
4. `DRY_RUN=True` 时，`executor.py` 只能打印，不能调用 `place_equity_order` / `place_crypto_order` / `place_option_order`。
5. `DRY_RUN=False` 时，每笔真实下单前必须先调 `review_equity_order`，把预估成本和 alert 写进日志，再 `place_equity_order`（带幂等 `ref_id`）。
6. 每次信号判断（含 HOLD）都要写入 `decisions.csv`，带 `reason` 字段。
7. `.env` 不进 git。MCP 的 OAuth token 由 Claude Code 自己管理，不出现在代码/对话/日志里。本项目已不需要任何 Robinhood 账号密码。

## 风控参数（数值见 config.py，推导理由见 docs/strategy-design.md）
单标的仓位 ≤25% ｜ 止损 -6% ｜ 单日最大亏损 -3% ｜ 单日最多2笔交易

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

## 当前策略版本
技术面 MA10/MA30 + 财报避雷（财报前2天不开仓）。标的池：AVGO / NVDA / MU / QQQ。
- **入场**（事件驱动）：仅"刚发生金叉"那根 bar 买入，不追高。
- **离场**（状态驱动）：持仓且 MA10 < MA30 就清仓，不等新死叉。
- **止损**（优先级最高）：持仓浮亏 ≤ -6% 强制清仓，用实时价，不受频率限制。
数据全部来自 MCP：价格 `get_equity_historicals`，财报 `get_earnings_calendar` / `get_earnings_results`，新闻 `get_equity_news`。**不再依赖 yfinance / Finnhub / 任何外部 API key。**
新闻情绪层仅每日生成参考，不接入自动决策。完整设计理由见 `docs/strategy-design.md`（只在需要调整策略逻辑时读）。

## 按需读取（不要默认加载，用到时才读）
- `docs/account-setup.md` — MCP 接入、账户确认、认证方式，仅当 MCP/账户相关出问题时读
- `docs/strategy-design.md` — 四层策略设计的完整讨论和取舍理由，仅当调整 strategy.py 逻辑时读
- `docs/execution-checklist.md` — 阶段A-E上线清单，仅当推进到新阶段时读
