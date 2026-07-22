# DEMO_READINESS.md

Date: 2026-07-22. Method: backend started cold via `uvicorn main:app --port 8000` and every endpoint exercised over real HTTP. Verdicts below are from observed responses, not code intent.

**Scope note, stated up front:** I exercised the backend directly over HTTP and read the exact payloads each page consumes. I did **not** click through the live UI, because the app gates every protected route behind Supabase auth (`AuthProvider` redirects unauthenticated users to `/auth/login`), and signing in would require creating or entering credentials, which I do not do. Page verdicts are therefore derived from (a) a clean production build and (b) the observed API responses each page renders. Where that distinction matters, I say so.

---

## The one environmental fact that shapes everything

**The Finnhub API key returns `401 Invalid API key` on every REST endpoint** — verified directly against `search`, `quote`, and `news`. This is the key flagged for rotation in prior sessions; it is now dead. Cascade, all observed:

- **Symbol search** → empty (search is a Finnhub call)
- **Events feed** → empty (`/api/events` reads Finnhub news)
- **Dashboard macro-events table** → empty (same source)
- **US quotes** → **unaffected**: the provider fails Finnhub over to AlphaVantage automatically (observed AAPL served by AlphaVantage)

The Finnhub **websocket** also loops `HTTP 401 ... reconnecting in 5s` in the server log. Background service, not a request path, but it's noisy in the console if the demo shows server logs.

Cold start otherwise: server healthy in ~1s, `/api/health` → 200.

---

## Per-feature observations

### Dashboard — DEMO READY (one empty sub-panel)
- Loads, no error. Main chart `^NSEI` 1D → **4,622 real candles**.
- Market Overview tickers: `^NSEI` 24028, `BTC` 65925, `^GSPC` — all real (yfinance / CoinGecko).
- Sector momentum: IT −0.44%, Banking −0.8% — **real** (yfinance XLK/XLF ETFs).
- Live Macro Events table: **empty** (Finnhub 401). Renders "No events available."
- Happy path: all 200s. No 4xx/5xx.

### Symbol search — DEMO PARTIAL → **avoid on stage**
- Returns `{"symbols":[]}` for `AAPL`, `reliance`, everything. HTTP 200, no error, no crash — but no results.
- Missing because: Finnhub `/search` → 401.
- One-liner: *"Search is offline — the news/search provider key expired; we navigate from the dashboard and picks instead."*

### Symbol page — US (AAPL) — DEMO READY
- Quote: **327.74, real, via AlphaVantage** (Finnhub failed over cleanly).
- Fundamentals: real — dayHigh 329.60, 52w 201.50–334.99, mktcap 4.81T, P/E 39.53, sector Technology, "Apple Inc."
- Chart: 11,492 real daily candles (also verified 1H → 5,073).
- Reached via a link carrying `?market=US`. Loads, 200s.

### Symbol page — NSE (RELIANCE.NS) — DEMO READY
- Quote: **₹1290.50, real, via yfinance.**
- Fundamentals: real — 52w 1253–1611, mktcap 17.46T, P/E 23.74, sector Energy, "Reliance Industries Limited".
- Chart: 7,669 real daily candles.

### Symbol page — CRYPTO (BTC) — DEMO READY
- Quote: **$65,958, real, via CoinGecko.**
- Chart: 4,326 real daily candles.
- Fundamentals: price/day-range/marketCap real ("Bitcoin USD", mktcap 1.32T). P/E shows `0` and sector "Unknown" — expected for crypto, renders as a dash / "Unknown", not an error.

### Charts — DEMO READY
- Every market × timeframe returned real OHLCV: AAPL 1D/1H, RELIANCE 1D, BTC 1D, ^NSEI 1D. Candle counts in the thousands. NaN gap-rows are dropped server-side; no serialization errors.

### Fundamentals — DEMO READY
- US and NSE full and real. Crypto partial-but-clean (no P/E, as above).

### Watchlist add / list / remove / persist — DEMO READY
- Full lifecycle observed against Supabase:
  - list initial `[]` → add AAPL/US `{"status":"added"}` → add BTC/CRYPTO `added` → **duplicate AAPL → 200 `added` (idempotent, no 503)** → list shows both with real Supabase UUIDs and timestamps → remove AAPL `{"status":"removed"}` → list shows only BTC.
- Persisted to Supabase (real rows, not in-memory).
- Rows hydrate price/change client-side via the quote endpoint, which is live — so watchlist rows show real quotes; a symbol whose quote fails shows a neutral dash (no red down-signal).

### Paper trade place / list / close — DEMO READY
- Portfolio: real Supabase row — balance 100000.00, realized_pnl 0, win_rate 0.
- Place AAPL LONG @300 → persisted with UUID, `status: open`.
- List → open_trades 1.
- Close → `{"status":"success"}`, `closed_manual`; list → open 0, closed 1.
- Caveat: a **manually closed** trade records no exit price, so its realized PnL renders as a dash in Trade History (not a fabricated 0). Fine to show; just don't claim a P&L number on manual closes.

### Positions with live marks — DEMO READY
- With an open position, the page fetches a live mark per symbol (quote endpoint works) and computes unrealized PnL from the real price. Verified the inputs: open AAPL @300 + live mark 327.74 → unrealized `+277.40` on 10 units.
- A position whose quote is unavailable shows a dash, never entry-price-as-mark.

### Picks — DEMO READY (mind the latency)
- **US**: 200, 2 real validated picks (AAPL LONG 319.45–323.19, target 351.23; both within the 20% band of the live price). **Took ~14 seconds** — two per-candidate LLM calls, sequential.
- **NSE**: 200, 2 real picks (RELIANCE.NS LONG 1277.79–1303.61). ~1.7s.
- No 4xx/5xx. The empty-pick problem from earlier audits is gone — levels are grounded in the live quote and pass validation.
- One-liner if US is slow on stage: *"It's making a live model call per symbol against the current price — a few seconds."*

### Events feed — DEMO PARTIAL
- `/api/events` → `{"events":[], "total":0}`. HTTP 200. Renders "No events available."
- Missing because: Finnhub news → 401.
- One-liner: *"The events feed pulls from a news provider whose key expired; the analysis engine behind it still works."*

### Events impact analysis — DEMO PARTIAL → **unreachable by clicking**
- Hit **directly** (`/api/events/123/impact`), it returns **real LLM output**: severity Medium, a written analysis, a populated chain_reaction. The engine works.
- But in the UI you reach it only by selecting an event in the feed, and the feed is empty — so there is **no click path to it**. Functional, not demoable through the UI.
- One-liner if asked: *"The impact analysis is live model output; it's gated behind the events feed, which is down with the provider key."*

### Alerts — DEMO PARTIAL
- `/api/alerts` → `{"alerts":[]}`, hardcoded empty, 200. Always empty by design; the alert agent's output is only logged, never surfaced. Nothing to show.

---

## Classification summary

| Feature | Verdict | Say-out-loud (if PARTIAL) |
|---|---|---|
| Dashboard | **DEMO READY** | (events sub-table empty; rest is real) |
| Symbol search | **DEMO PARTIAL** | "Search is offline — provider key expired; navigate from dashboard/picks." |
| Symbol page — US (AAPL) | **DEMO READY** | |
| Symbol page — NSE (RELIANCE.NS) | **DEMO READY** | |
| Symbol page — CRYPTO (BTC) | **DEMO READY** | |
| Charts (all markets) | **DEMO READY** | |
| Fundamentals | **DEMO READY** | |
| Watchlist add/list/remove/persist | **DEMO READY** | |
| Paper place/list/close | **DEMO READY** | |
| Positions w/ live marks | **DEMO READY** | |
| Picks — US | **DEMO READY** | (~14s; "a live model call per symbol") |
| Picks — NSE | **DEMO READY** | |
| Events feed | **DEMO PARTIAL** | "News-provider key expired; feed is empty." |
| Events impact analysis | **DEMO PARTIAL** | "Engine works, but it's gated behind the empty feed." |
| Alerts | **DEMO PARTIAL** | "No alerts surface to the UI yet." |

### DO NOT CLICK (dead nav — these routes do not exist in the build)
The production build emitted only: `/`, `/auth/login`, `/auth/signup`, `/dashboard`, `/events`, `/events/[id]`, `/paper`, `/picks`, `/symbol/[ticker]`, `/watchlist`. The sidebar links to three routes that are **not** in that list:
- **Trade History → `/paper/history`** — not built → 404
- **Macro Scanner → `/scanner`** — not built → 404
- **Health Status → `/health`** — not built → 404

Do not click these in the sidebar. Also avoid **symbol search** (empty) and any **event row** (there are none; the impact panel can't be reached).

**Auth prerequisite:** protected pages redirect to `/auth/login` when no session exists. You must be signed in *before* the demo starts. I did not exercise the sign-in flow (it needs credentials), so treat the live login itself as unverified — log in and confirm you land on `/dashboard` before going on stage.

---

## Recommended click sequence (maximizes DEMO READY, never touches a DO NOT CLICK path)

Pre-flight (before anyone is watching): sign in, confirm you land on `/dashboard`.

1. **Dashboard** — land here. Point at the live `^NSEI` candle chart, the three real index/crypto tickers, and the real sector-momentum bars. (Don't dwell on the empty events table below.)
2. On the dashboard chart, click the built-in symbol buttons **S&P 500**, **Bitcoin**, **Gold**, back to **Nifty 50** — these switch the chart via direct calls, no search needed. Real candles each time.
3. Left nav → **AI Picks**. Select market **NSE** first (fast, ~2s) — real picks render with entry zone / target / stop / confidence. Then switch to **US** and warn it's a few seconds (live model call per symbol). Real picks render.
4. On a pick row, click the **ticker link** (e.g. RELIANCE.NS) → opens the **Symbol page** with `?market=NSE` already attached. Live ₹ quote, real fundamentals, real chart. Toggle a couple of timeframes.
5. Back to a pick → click **Simulate** → **Place Order**. Confirms a paper trade against the live-grounded entry.
6. Left nav → **Paper Portfolio**. The position you just opened shows a **live current price and a real unrealized P&L** (mark pulled live). Real virtual balance up top. Click **Close** on the position — it moves to Trade History.
7. Left nav → **Watchlist**. If empty, add one via the flow you trust (from a symbol page's watchlist action, since search is down). Rows show live price/change. Remove one to show it persists.

That path hits: dashboard (chart + tickers + sectors), charts across 4 symbols, NSE + US picks, a symbol page (NSE), paper place + live-mark position + close, and watchlist list/remove — all DEMO READY, all real data.

**Symbols to use:** NSE `RELIANCE.NS`, US `AAPL`, crypto `BTC`, index `^NSEI`/`^GSPC` — all confirmed to return real quotes, fundamentals, and charts this session. Avoid typing anything into search.

---

## Final checks

- **Tests: 51 passed** (`pytest -q` → `51 passed, 1 warning`). Confirmed.
- **Frontend build: clean** (`npm run build` → `✓ Compiled successfully`, all 11 routes emitted). Confirmed.
- **Working trees: NOT clean.** Reporting honestly:
  - **Backend repo:** `AGENT_INVENTORY.md` untracked (last session's deliverable, never committed); `.claude/settings.local.json` modified (harness file). This new file `DEMO_READINESS.md` will also be untracked.
  - **Frontend repo:** `src/app/auth/login/page.tsx`, `src/app/auth/signup/page.tsx`, `src/components/AuthProvider.tsx`, `src/components/Sidebar.tsx` modified, plus `public/sw.js` (PWA build artifact). These are pre-existing uncommitted edits — I changed no code this session — and they build clean. The auth files wire to real Supabase auth (`signInWithPassword`, `signUp`, `signOut`); `AuthProvider` gained a `logout` used by the `Sidebar`. Worth committing (or stashing) before the demo so the tree is a known state, but nothing here is broken.
