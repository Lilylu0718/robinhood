# robinhood-bot

$1000 的 Robinhood 自动交易实验（观察 ≤1 个月）。策略、风控、上线阶段见 `CLAUDE.md` 和 `docs/`。

- 交易通道：官方 Robinhood Agentic Trading MCP（`agent.robinhood.com/mcp/trading`）
- 实验账户：Agentic 账户 `414480244`（唯一 `agentic_allowed`）。主账户等其它账户只读、永不下单。
- 策略：MA10/MA30（入场认新金叉、离场认状态）+ 财报前2天避雷。标的池 AVGO/NVDA/MU/QQQ。
- 运行：云端 routine 按 cron 唤醒 Claude agent，跑 `main.py` 的 RUNBOOK；DRY_RUN 阶段只记录不下单。

## 本地开发

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python3 -m pytest -q
```

`data.py` / `strategy.py` / `risk.py` / `logger.py` 是纯函数、不发 MCP 请求；MCP 调用由 agent 会话完成，把 response 喂进 `main.run_pipeline()`。
