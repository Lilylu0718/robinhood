#!/bin/bash
# 每周深度任务：复盘 + 扩池扫描 + 投资档案/买入区间。launchd 周五 13:30 PT 触发（收盘后，不和完整运行抢锁）。
set -uo pipefail
PROJECT="/Users/lilylu/robinhood-bot"
NTFY_TOPIC="rhbot-lily-8f3k2p"
cd "$PROJECT" || exit 1
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

LOCK="$PROJECT/.run.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +120 2>/dev/null)" ]; then rm -rf "$LOCK"; mkdir "$LOCK"; else exit 0; fi
fi
trap 'rm -rf "$LOCK"' EXIT
caffeinate -i -w $$ &

LOG_DIR="$PROJECT/logs"; mkdir -p "$LOG_DIR" "$PROJECT/research/reviews" "$PROJECT/research/theses"
LOG="$LOG_DIR/weekly-$(date +%Y%m%d-%H%M).log"
echo "=== $(date) weekly start ===" | tee -a "$LOG"
for n in $(seq 1 40); do curl -s --max-time 5 -o /dev/null https://api.anthropic.com && break; sleep 15; done
git pull --quiet --rebase 2>&1 | tee -a "$LOG" || true

OUT=""
for i in 1 2; do
  # prompt 放在 --disallowedTools 前面（该参数是变长的）
  OUT="$(claude --print --permission-mode default "$(cat "$PROJECT/weekly_prompt.md")" \
    --disallowedTools mcp__claude_ai_robinhood__review_equity_order mcp__claude_ai_robinhood__place_equity_order mcp__claude_ai_robinhood__place_advanced_order \
    2>&1 | tee -a "$LOG")"
  echo "$OUT" | grep -q "WEEKLY_DONE" && break
  echo "$OUT" | grep -q "RH_MCP_AUTH_EXPIRED" && break
  echo "--- weekly attempt $i failed, retry in 120s ---" | tee -a "$LOG"; sleep 120
done
echo "=== $(date) weekly done ===" | tee -a "$LOG"

if echo "$OUT" | grep -q "WEEKLY_DONE"; then
  TITLE="📊 robinhood-bot 周报 $(date +%m-%d)"; PRI="default"
  BODY="$(echo "$OUT" | grep -v WEEKLY_DONE | tail -n 15)"
else
  TITLE="⛔ robinhood-bot 周任务没跑成 $(date +%m-%d)"; PRI="high"
  BODY="看 $LOG"
fi
curl -s --max-time 15 -H "Title: $TITLE" -H "Priority: $PRI" -d "$BODY" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
