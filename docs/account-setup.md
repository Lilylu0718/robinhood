# 账户与接入设置（一次性记录，出问题时再读）

## 背景（2026-09 更新：改用官方 Agentic Trading）
早期方案用 `robin_stocks`（逆向工程库，违反 ToS，有账户被限制的理论风险）。排查中发现：
- `robin_stocks` 用的是 Robinhood 2015 年的 legacy password-grant OAuth 客户端 + 逆向 REST 接口。
- Robinhood 的"多个个人投资账户"功能 2026-09 才 rollout，legacy 接口没更新，`/accounts/` 对该客户端**只返回 primary 账户**（`624891156`）。全新 token 也一样。
- 因此 `robin_stocks` 这条路**够不着实验账户**，已弃用。

改用 **Robinhood 官方 Agentic Trading**（2026-05 上线）：一个独立隔离的券商账户，AI agent 通过官方 MCP server 连接。官方授权，不违反 ToS；agent 只能在该账户下单，不能转出资金。

## 账户清单（`get_accounts` 返回，2026-09-10）
| account_number | 昵称 | 类型 | agentic_allowed | 用途 |
|---|---|---|---|---|
| `624891156` | *(无)* | margin | false | 主账户。VOO/VTI 定投 + 手动持仓（NVDA/GOOGL/MSFT/AXP）+ SPCX 挂单。**只读，永不下单。** |
| `554410696` | Summer fling | cash | false | 早期开的第二个 individual 账户，本项目不用。只读。 |
| **`414480244`** | **Agentic** | limited_margin | **true** | **本实验账户。** $1000 本金，agent 唯一可下单的账户。 |

- 账户持有人：Yulei Lu / `luyulei0718@gmail.com` / 用户名 `yuleil61636229871595`。
- `414480244` 状态（2026-09-10）：cash $1000，buying_power $1000，0 持仓，0 挂单。
- 类型是 `limited_margin`（Robinhood agentic onboarding 默认），不是纯 cash。策略不上杠杆，风控参数按无杠杆写；limited margin 主要影响资金即时结算，不影响策略逻辑。

## MCP 接入
```
claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading
```
然后在 Claude Code 会话里 `/mcp` → 选 `robinhood-trading` → 认证（浏览器 OAuth，登录 Robinhood 授权）。首次认证会触发 Agentic 账户 onboarding（桌面端完成）。

- 配置写在 `/Users/lilylu/.claude.json` 项目级 `mcpServers`。
- 新加 MCP server 后当前会话不生效，要 `claude --continue` 重启会话才出现在 `/mcp` 菜单里。
- OAuth token 由 Claude Code 管理，会过期，过期后重新 `/mcp` 认证。
- 项目**不再需要** `.env` 里的 Robinhood 账号密码。若将来引入别的外部数据源才需要 `.env`。

## 可用 MCP 工具（挑本项目会用的）
- 只读：`get_accounts` `get_portfolio` `get_equity_positions` `get_equity_orders` `get_equity_quotes` `get_equity_historicals` `get_earnings_calendar` `get_earnings_results` `get_equity_news` `get_equity_fundamentals` `get_realized_pnl` `get_pnl_trade_history`
- 下单：`review_equity_order`（模拟+alert，下单前必调）→ `place_equity_order`（真实，带 `ref_id` 幂等）→ `cancel_equity_order`
- 期权/加密：本项目不用。

## 安全事件记录
账户密码曾经一次性打进过聊天对话框，已经改过密码。现在改用 MCP OAuth，项目里已无账号密码。此后所有密码/密钥只在终端手动输入，不再出现在任何对话里。
