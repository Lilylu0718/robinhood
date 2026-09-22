#!/bin/bash
# robinhood-bot 每日执行包装脚本。由 launchd 触发。
# 跑 `claude -p` 执行 daily_prompt.md 的 RUNBOOK，结果记日志 + 桌面通知 + 手机推送(ntfy)。
set -uo pipefail

PROJECT="/Users/lilylu/robinhood-bot"
NTFY_TOPIC="rhbot-lily-8f3k2p"   # 手机装 ntfy app 订阅这个 topic
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
# 外层重试：整次跑失败（多半是 MCP/DNS 连接问题，prompt 内部已经自己重试过一轮）就整个 claude --print 再来一次，
# 带退避，最多 3 次尝试。用 last_run.md 的 mtime + 内容日期判断这次是否真的成功写了今天的结果。
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
TODAY_LOCAL="$(date +%Y-%m-%d)"
LAST_RUN_MD="$PROJECT/last_run.md"
PREV_MTIME="$(stat -f %m "$LAST_RUN_MD" 2>/dev/null || echo 0)"

MAX_ATTEMPTS=3
BACKOFFS=(0 60 180)   # 秒：第1次不等，第2次等60s，第3次等180s
SUCCESS=0
SUMMARY=""

for i in $(seq 1 $MAX_ATTEMPTS); do
  wait_s="${BACKOFFS[$((i-1))]}"
  if [ "$wait_s" -gt 0 ]; then
    echo "--- attempt $i/$MAX_ATTEMPTS, waiting ${wait_s}s first ---" | tee -a "$LOG"
    sleep "$wait_s"
  else
    echo "--- attempt $i/$MAX_ATTEMPTS ---" | tee -a "$LOG"
  fi

  SUMMARY="$(claude --print --permission-mode default \
    "$(cat "$PROJECT/daily_prompt.md")" 2>&1 | tee -a "$LOG" | tail -n 12)"

  NEW_MTIME="$(stat -f %m "$LAST_RUN_MD" 2>/dev/null || echo 0)"
  if [ "$NEW_MTIME" != "$PREV_MTIME" ] && head -1 "$LAST_RUN_MD" 2>/dev/null | grep -q "$TODAY_LOCAL"; then
    SUCCESS=1
    echo "--- attempt $i succeeded (last_run.md updated for $TODAY_LOCAL) ---" | tee -a "$LOG"
    break
  fi
  echo "--- attempt $i did not produce today's last_run.md, will retry if attempts remain ---" | tee -a "$LOG"
done

if [ "$SUCCESS" -ne 1 ]; then
  echo "!!! all $MAX_ATTEMPTS attempts failed to complete today's run !!!" | tee -a "$LOG"
fi

echo "=== $(date) done (success=$SUCCESS) ===" | tee -a "$LOG"

# 通知：Mac 桌面横幅 + 手机 ntfy 推送
if [ "$SUCCESS" -eq 1 ]; then
  TITLE="robinhood-bot $(date +%m-%d\ %H:%M)"
  BODY="$(sed -n '3,12p' "$PROJECT/last_run.md" 2>/dev/null)"
else
  TITLE="⛔ robinhood-bot 今天没跑成 $(date +%m-%d\ %H:%M)"
  BODY="重试 $MAX_ATTEMPTS 次都没写出今天的 last_run.md，多半是 MCP/网络连接问题。看 $LOG"
fi
[ -z "$BODY" ] && BODY="$SUMMARY"

osascript -e "display notification \"$(echo "$BODY" | tr '\n' ' ' | sed 's/"/'"'"'/g')\" with title \"$TITLE\"" 2>/dev/null || true

if [ "$SUCCESS" -eq 1 ]; then
  NTFY_TAG="chart_with_upwards_trend"
  NTFY_PRIORITY="default"
else
  NTFY_TAG="x"
  NTFY_PRIORITY="high"
fi
curl -s --max-time 15 \
  -H "Title: $TITLE" \
  -H "Tags: $NTFY_TAG" \
  -H "Priority: $NTFY_PRIORITY" \
  -d "$BODY" \
  "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true

# 日志保留最近 60 个
ls -1t "$LOG_DIR"/run-*.log 2>/dev/null | tail -n +61 | xargs -r rm -f
