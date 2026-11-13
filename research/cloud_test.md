# Cloud smoke test — 2026-11-13 07:01 UTC

1. git: PASS — main at a012144 (Docs: bot now runs in cloud routines; Mac launchd jobs disabled)
2. python: PASS — 50 passed in 0.45s
3. config: PASS — DRY_RUN=False, SYMBOLS=GOOGL AAPL NVDA AVGO MSFT AMZN META MU QQQ TSM NOW CRM
4. robinhood: PASS — agentic_allowed only on 414480244; total value $2983.56 (equity $1479.23, cash $1504.33); holds PURR GOOGL QQQ AMZN META MU NVDA AVGO; NVDA last $166.04 (after-hours $165.00, prev close $166.19)
5. web: PASS (weak) — search worked but no dated "today" headline; top result MarketBeat NVDA news page
6. git push: see commit
7. ntfy: FAIL — HTTP 000 (blocked by cloud network, expected)
