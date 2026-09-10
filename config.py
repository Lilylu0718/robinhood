"""所有可调参数。改这里，不要把常量散到别的文件。"""

# ── 账户 ─────────────────────────────────────────────────────────────
# Robinhood Agentic 实验账户（昵称 "Agentic"）。只有这个账户 agentic_allowed=true。
# 主账户 624891156 / "Summer fling" 554410696 永不下单。
ACCOUNT_NUMBER = "414480244"

# 主账户和其它账户，用于代码里做"绝不等于"断言。
FORBIDDEN_ACCOUNTS = ("624891156", "554410696")

# ── 运行开关 ─────────────────────────────────────────────────────────
# True：executor 只打印，绝不调用真实下单工具。切 False 前走完阶段 D。
DRY_RUN = True

# ── 标的池 ───────────────────────────────────────────────────────────
SYMBOLS = ("AVGO", "NVDA", "MU", "QQQ")

# ── 策略参数 ─────────────────────────────────────────────────────────
MA_FAST = 10          # 快线周期（日）
MA_SLOW = 30          # 慢线周期（日）
HIST_LOOKBACK_DAYS = 90   # 拉多少日历天的日线（要 ≥ MA_SLOW + 交叉判断余量）

# 财报避雷：财报日前 N 个自然日内不开新仓（不影响平仓/止损）
EARNINGS_BLACKOUT_DAYS = 2
# verified=false 的财报日期也按避雷处理（宁可错过）
EARNINGS_TREAT_TENTATIVE_AS_REAL = True

# ── 风控参数（推导理由见 docs/strategy-design.md）─────────────────────
MAX_POSITION_PCT = 0.25      # 单标的市值 ≤ 组合总值的 25%
STOP_LOSS_PCT = -0.06        # 持仓浮亏 ≤ -6% 触发止损卖出
MAX_DAILY_LOSS_PCT = -0.03   # 当日组合亏损达 -3%，当天停止一切开仓
MAX_TRADES_PER_DAY = 2       # 当日最多 2 笔成交（买+卖合计）

# 单笔开仓目标金额 = 组合总值 * TARGET_POSITION_PCT（受 MAX_POSITION_PCT 上限约束）
TARGET_POSITION_PCT = 0.20

# ── 文件 ─────────────────────────────────────────────────────────────
DECISIONS_CSV = "decisions.csv"
EQUITY_CSV = "equity.csv"
