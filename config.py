"""所有可调参数。改这里，不要把常量散到别的文件。"""

# ── 账户 ─────────────────────────────────────────────────────────────
# Robinhood Agentic 实验账户（昵称 "Agentic"）。只有这个账户 agentic_allowed=true。
# 主账户 624891156 / "Summer fling" 554410696 永不下单。
ACCOUNT_NUMBER = "414480244"

# 主账户和其它账户，用于代码里做"绝不等于"断言。
FORBIDDEN_ACCOUNTS = ("624891156", "554410696")

# ── 运行开关 ─────────────────────────────────────────────────────────
# True：executor 只打印，绝不调用真实下单工具。
DRY_RUN = False   # 2026-11-02 用户要求立即真钱交易

# ── 标的池 ───────────────────────────────────────────────────────────
SYMBOLS = ("AVGO", "NVDA", "MU", "QQQ", "GOOGL", "AAPL")
ETF_SYMBOLS = ("QQQ",)   # ETF 波动小，抄底回撤阈值单独设

# 用户手动指定的长期持有仓位：不进策略池、不触发止损、bot 永不卖出（2026-11-02 用户决定）
LONG_TERM_HOLDS = ("PURR",)

# ── 策略参数（抄底 / 均值回归，2026-11-02 起）──────────────────────────
DIP_LOOKBACK = 20            # 回撤基准：近 20 个交易日最高收盘
DIP_DRAWDOWN_STOCK = 0.08    # 个股：较 20 日高回撤 ≥ 8% 才算"底"
DIP_DRAWDOWN_ETF = 0.05      # ETF：≥ 5%
RSI_PERIOD = 14
DIP_RSI_MAX = 40             # 且 RSI(14) ≤ 40（超卖）
REBOUND_MA = 20              # 反弹到 MA20 视为均值回归完成
TAKE_PROFIT_PCT = 0.10       # 浮盈 ≥ 10% 止盈
REBOUND_MIN_PROFIT_PCT = 0.03  # 站回 MA20 时浮盈 ≥ 3% 才走
HIST_LOOKBACK_DAYS = 90      # 拉多少日历天的日线

# 财报避雷：财报日前 N 个自然日内不开新仓（不影响平仓/止损）
EARNINGS_BLACKOUT_DAYS = 2
# verified=false 的财报日期也按避雷处理（宁可错过）
EARNINGS_TREAT_TENTATIVE_AS_REAL = True

# ── 风控参数（推导理由见 docs/strategy-design.md）─────────────────────
MAX_POSITION_PCT = 0.25      # 单标的市值 ≤ 组合总值的 25%
STOP_LOSS_PCT = -0.15        # 持仓浮亏 ≤ -15% 触发止损卖出（抄底需要空间，2026-11-02 用户从 -6% 放宽）
MAX_DAILY_LOSS_PCT = -0.03   # 当日组合亏损达 -3%，当天停止一切开仓
MAX_TRADES_PER_DAY = 2       # 当日最多 2 笔成交（买+卖合计）

# 单笔开仓目标金额 = 组合总值 * TARGET_POSITION_PCT（受 MAX_POSITION_PCT 上限约束）
TARGET_POSITION_PCT = 0.20

# ── 文件 ─────────────────────────────────────────────────────────────
DECISIONS_CSV = "decisions.csv"
EQUITY_CSV = "equity.csv"
