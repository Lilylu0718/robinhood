# 执行清单（推进到新阶段时读，其余时候不用管）

> 2026-09 路线调整：弃用 `robin_stocks`，改用官方 Robinhood Agentic Trading MCP。详见 account-setup.md。

### 阶段 A｜账户与接入收尾 ✅
- [x] 加 `robinhood-trading` MCP server，`/mcp` 认证成功
- [x] 完成 Agentic 账户 onboarding，账户 `414480244`（昵称 "Agentic"）
- [x] $1000 已到位（`get_portfolio` 确认 cash $1000 / buying_power $1000 / 0 持仓 / 0 挂单）
- [x] `get_accounts` 确认只有 `414480244` 的 `agentic_allowed=true`
- [x] 弃用 robin_stocks：删 test_login.py，venv 卸载 robin-stocks / pyotp

### 阶段 B｜项目结构搭建 ✅
- [x] 按 CLAUDE.md 文件结构建 7 个文件
- [x] `config.py`：`ACCOUNT_NUMBER = "414480244"`、`DRY_RUN = True`、风控/策略常量
- [x] `data.py` / `strategy.py` / `risk.py` / `logger.py` 写成纯函数（不发 MCP 请求）
- [x] `main.py`：`run_pipeline()` 编排 + 顶部 RUNBOOK 写清 MCP 取数步骤

### 阶段 C｜逐层实现（每层单独测试）
- [x] `data.py`：解析 historicals / earnings / quotes / portfolio / positions / orders，单测（fixtures 用真实录样）
- [x] `strategy.py`：MA10/MA30 交叉 + 财报避雷，每个信号带 `reason`，单测
- [x] `risk.py`：仓位/止损/日亏/频率检查，单测
- [x] `executor.py`：DRY_RUN 打印分支完整；真实分支产出 OrderPlan + `assert_account_safe`，单测
- [x] `logger.py`：决策（含HOLD）写 `decisions.csv`，每日市值写 `equity.csv`
- [x] 跑一次完整 DRY_RUN：真实 MCP 数据（2026-09-10）→ 4 标的全 HOLD（无交叉）→ 无下单，CSV 正常
- [ ] （可选）录更多 fixture：金叉/死叉/持仓/止损场景，锁进单测

### 阶段 D｜纸面验证（1-2周，DRY_RUN=True）— 进行中
- [~] 每天跑一次主流程，检查 `decisions.csv` 输出是否合理
  - Day 1（2026-09-10）：4 标的全 HOLD。AVGO 空头排列；NVDA/MU/QQQ 多头排列但无新金叉→不追高。无下单。
- [ ] 财报避雷触发时机、仓位/止损计算、重复信号——逐项核对
- [ ] 核对 MCP 数据质量：`get_equity_historicals` 的 MA 值 vs 别处交叉验证一次
- [ ] 发现bug回阶段C修，不跳过验证直接上线

### 调度（2026-09 定）
- 云端 routine **不可行**：自定义 MCP 连接器无 UUID 发现路径、且不会注入云端 agent 会话
  （claude-code issue #63233 / #42175 / #61196）。
- 改用**本地 launchd**：`com.lilylu.robinhood-bot.plist` → `run_daily.sh` → `claude --print daily_prompt.md`。
  工作日 10:00 + 13:15 PT（美东 13:00 / 16:15）。Mac 睡着跳过、醒来补一次。
- 安装：`cp com.lilylu.robinhood-bot.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.lilylu.robinhood-bot.plist`
- 想真 24/7：把这套丢到一台常开机器上。
- `.claude/settings.json` 里 place_/cancel_ 类工具在 `deny`，headless 跑不可能误下单。

### 阶段 D｜纸面验证（跑起来了才算数）
- [ ] launchd 装好，连续几个交易日 `decisions.csv` / `last_run.md` 有正常输出
- [ ] 每天看一眼通知/`last_run.md`

### 阶段 E｜切换真实下单
- [ ] 纸面 1-2 周干净后再动
- [ ] 定 agent 下单模式：每单人工确认 vs 授权自主（Robinhood agentic 设置里）
- [ ] `config.py` 的 `DRY_RUN` 改成 `False`；`daily_prompt.md` 第 3 步补 review→place
- [ ] `.claude/settings.json` 把 `place_equity_order` 从 deny 挪走（按下单模式决定 allow 还是 ask）
- [ ] 上线第一天手动盯着跑一次
- [ ] 进入日常节奏直到满1个月，对照 strategy-design.md 的评估标准复盘
