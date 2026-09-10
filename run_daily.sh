#!/bin/bash
# robinhood-bot 每日执行包装脚本。由 launchd 触发。
# 跑 `claude -p` 执行 daily_prompt.md 的 RUNBOOK，结果记日志 + 桌面通知。
set -uo pipefail

PROJECT="/Users/lilylu/robinhood-bot"
cd "$PROJECT" || exit 1

LOG_DIR="$PROJECT/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/run-$STAMP.log"

echo "=== $(date) start ===" | tee -a "$LOG"

# 只在美股交易日 + 大致交易时段附近跑（周末直接跳过；launchd 时间点已限制在工作日）
DOW="$(date +%u)"   # 1=Mon .. 7=Sun
if [ "$DOW" -gt 5 ]; then
  echo "weekend, skip" | tee -a "$LOG"
  exit 0
fi

# 拉最新代码（策略/配置可能在别处改过）
git pull --quiet --rebase 2>&1 | tee -a "$LOG" || true

# 跑 Claude 无人值守。--print 非交互；权限走 .claude/settings.json 白名单。
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
SUMMARY="$(claude --print --permission-mode default \
  "$(cat "$PROJECT/daily_prompt.md")" 2>&1 | tee -a "$LOG" | tail -n 12)"

echo "=== $(date) done ===" | tee -a "$LOG"

# 桌面通知（macOS）。手机推送需要 Remote Control 常驻，另配。
TITLE="robinhood-bot $(date +%m-%d\ %H:%M)"
BODY="$(sed -n '1,4p' "$PROJECT/last_run.md" 2>/dev/null | tr '\n' ' ')"
[ -z "$BODY" ] && BODY="$SUMMARY"
osascript -e "display notification \"${BODY//\"/\'}\" with title \"$TITLE\"" 2>/dev/null || true

# 日志保留最近 60 个
ls -1t "$LOG_DIR"/run-*.log 2>/dev/null | tail -n +61 | xargs -r rm -f
