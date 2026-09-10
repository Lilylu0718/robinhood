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

### 阶段 E｜切换真实下单
- [ ] 定调度方式：cron 跑 `claude -p "跑今天的交易流程"` / `schedule` skill 建 routine / 手动每天触发——选一个
- [ ] 定 agent 下单模式：每单人工确认 vs 授权自主下单（Robinhood agentic 设置里）
- [ ] `config.py` 的 `DRY_RUN` 改成 `False`
- [ ] 上线第一天手动盯着跑一次（`review_equity_order` 的 alert 逐条看）
- [ ] 进入日常节奏直到满1个月，对照 strategy-design.md 的评估标准复盘
