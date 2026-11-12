#!/bin/bash
# 盯盘：launchd 每 30 分钟触发。只在工作日 6:30–13:00 PT 干活；发现异动/新消息就追加一次完整运行（run_daily.sh）。
set -uo pipefail
PROJECT="/Users/lilylu/robinhood-bot"
NTFY_TOPIC="rhbot-lily-8f3k2p"
cd "$PROJECT" || exit 1
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

DOW="$(date +%u)"; HM="$(date +%H%M)"
[ "$DOW" -gt 5 ] && exit 0
{ [ "$HM" -lt 0630 ] || [ "$HM" -ge 1300 ]; } && exit 0
# 完整运行进行中就不打扰
[ -d "$PROJECT/.run.lock" ] && exit 0
# 防止两个盯盘叠在一起
WLOCK="$PROJECT/.watch.lock"
if ! mkdir "$WLOCK" 2>/dev/null; then
  [ -n "$(find "$WLOCK" -maxdepth 0 -mmin +14 2>/dev/null)" ] && { rm -rf "$WLOCK"; mkdir "$WLOCK"; } || exit 0
fi
trap 'rm -rf "$WLOCK"' EXIT
caffeinate -i -w $$ &
# 若早上的完整运行没跑（例如登录问题），盯盘也负责保持清醒到 13:45
END_S=$(date -j -f "%H:%M:%S" "13:45:00" +%s 2>/dev/null); NOW_S=$(date +%s)
if [ -n "$END_S" ] && [ "$END_S" -gt "$NOW_S" ] && ! pgrep -f "caffeinate -i -t" >/dev/null; then
  nohup caffeinate -i -t $((END_S - NOW_S)) >/dev/null 2>&1 &
fi

LOG_DIR="$PROJECT/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/watch-$(date +%Y%m%d-%H%M).log"
echo "=== $(date) watch start ===" >> "$LOG"

# 注意：prompt 必须放在 --disallowedTools 前面（该参数是变长的，会吞掉后面的 prompt）
OUT="$(claude --print --permission-mode default "$(cat "$PROJECT/watch_prompt.md")" \
  --disallowedTools mcp__claude_ai_robinhood__review_equity_order mcp__claude_ai_robinhood__place_equity_order mcp__claude_ai_robinhood__place_advanced_order \
  2>&1 | tee -a "$LOG")"
LINE="$(echo "$OUT" | grep -E '^WATCH_TRIGGER:' | tail -1)"
echo "=== $(date) watch done: $LINE ===" >> "$LOG"

if echo "$OUT" | grep -q "RH_MCP_AUTH_EXPIRED"; then
  curl -s --max-time 15 -H "Title: 🔑 robinhood-bot 盯盘：Robinhood 授权过期" -H "Priority: high" \
    -d "到 claude.ai → 设置 → 连接器 重新连接 Robinhood。" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
  exit 0
fi

if echo "$LINE" | grep -q "^WATCH_TRIGGER: yes"; then
  REASON="${LINE#WATCH_TRIGGER: yes }"
  curl -s --max-time 15 -H "Title: 👀 robinhood-bot 盯盘触发 $(date +%H:%M)" -H "Tags: eyes" \
    -d "$REASON — 正在追加一次完整研判+交易" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 || true
  rm -rf "$WLOCK"; trap - EXIT
  exec "$PROJECT/run_daily.sh"
fi

ls -1t "$LOG_DIR"/watch-*.log 2>/dev/null | tail -n +200 | xargs -r rm -f
