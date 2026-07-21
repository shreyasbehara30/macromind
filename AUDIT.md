# AUDIT.md

Audit date: 2026-07-21. Scope: `backend/` (FastAPI, Python 3.14 venv), `frontend/` (Next.js 16), root `*.html` prototypes.
Method: static read of every non-vendored source file, plus live execution of the FastAPI app via `TestClient` against the real API keys committed in `backend/.env`. Findings marked "verified" were executed; everything else is read from source.

No tests exist, so "does it run" was established by running it.

---

## 1. Component inventory

### Exchange ingestion and websocket handling — **STUB**

What exists:
- `backend/services/realtime/finnhub_ws.py` — Finnhub trade-tick websocket client, started from FastAPI `lifespan` in `backend/main.py:17`. Subscribes to a hardcoded list `["BINANCE:BTCUSDT","AAPL","MSFT","TSLA","NVDA"]` (`finnhub_ws.py:13`) with a comment that literally says "Mock list".
- `backend/services/realtime/polling.py` — APScheduler, 20s price poll over a hardcoded 4-symbol list (`polling.py:14-19`), 20s paper settlement sweep, 300s news poll.
- `backend/services/market_data/providers/` — REST quote providers: Finnhub → AlphaVantage → yfinance fallback chain (US), yfinance (NSE), CoinGecko (crypto).

What actually runs:
- REST quote fetching works. Verified live: AAPL `327.49` from Finnhub, RELIANCE.NS `1303.70` from yfinance, BTC `66246.0` from CoinGecko.
- The websocket ticks go nowhere useful. `_handle_trade` (`finnhub_ws.py:55`) writes a quote dict into Redis with **`change: 0.0` and `change_percent: 0.0` hardcoded** and a 60s TTL. Any consumer reading that cache key gets a real price with a fabricated zero change. `MarketDataService.get_quote` reads exactly that key first (`service.py:36-44`), so a US quote served from WS cache always reports 0.00 / 0.00% change.
- Redis is configured by string-munging a REST URL into a `rediss://` URI (`service.py:26-30`). Unverified — the Upstash host resolves, but the constructed credential form is a guess in the code's own comments.
- No order book, no L2/depth, no trade tape persistence. Ticks are used for one thing only: the anomaly check, then discarded.

### Database schema and what is persisted — **STUB**

- Schema exists as raw SQL only: `backend/services/paper_trading/schema.sql` — `paper_portfolio` (virtual balance, realized PnL) and `paper_trades` (ticker, direction, entry, qty, target, stop, status, realized_pnl). There is no migration runner; `implementation_plan.md` says the user is expected to paste it into the Supabase dashboard.
- A `watchlist` table is queried in `api/routes.py:348` but **is not in `schema.sql`** and is defined nowhere in the repo.
- **Nothing is persisted today.** Verified: `get_supabase()` → `ConnectError [Errno 11001] getaddrinfo failed` — the Supabase host in the committed config does not resolve, while Finnhub/CoinGecko/yfinance resolve fine from the same process. The project is dead or deleted.
- Every DB call site is wrapped in `try/except` that silently falls back to process-local Python lists: `IN_MEMORY_WATCHLIST` (`routes.py:339`), `IN_MEMORY_TRADES` / `IN_MEMORY_PORTFOLIO` (`api/paper.py:27-31`). These are lost on restart, not shared across workers, and are returned to the client with HTTP 200.
- Verified: `GET /api/paper/portfolio` → `{"virtual_balance":100000.0,...,"error":"Using in-memory data (Supabase offline)"}`. The frontend never reads that `error` field.
- Price history, ticks, events, and classifications are persisted **nowhere**. Every chart request re-downloads from yfinance.

### Backtesting logic of any kind — **ABSENT**

There is no backtest module, no historical simulation loop, no equity-curve computation, no Sharpe/drawdown/PnL statistics over historical data. Grep for `backtest|sharpe|walk-forward` across all non-vendored source returns nothing.

The nearest neighbour is `services/paper_trading/settlement.py`, which is a forward-only live poll loop, not a backtest. See §3 for the lookahead-adjacent problems it does have.

### ML or forecasting code — **ABSENT**

- No sklearn, torch, tensorflow, statsmodels, prophet, or any model file. `numpy`/`pandas` are present in the venv only as transitive dependencies of `yfinance`; no project code imports either.
- What is branded as AI is LLM prompting only: `services/agents/*` (four `AgentRunner` subclasses over Groq `llama-3.3-70b-versatile` / Gemini / Ollama) and `services/events/{classifier,impact}.py`.
- Of the four agents, three have tool sets that are **entirely fake**: `alert_monitoring.py:5-13`, `portfolio_impact.py:3-16`, and `macro_research.get_historical_analogues` (`macro_research.py:508`) all return hardcoded English strings marked `# Mock implementation`. The alert agent is the one wired to the live anomaly path, and its only tools return "RBI announces unexpected rate cut" regardless of input.
- `services/events/classifier.py` and `services/events/impact.py` are complete and unreferenced — **no route, job, or agent imports them.** Dead code.
- `services/agents/context_assembler.py` — the "RAG pipeline" — is also imported by nothing.
- The sidebar labels AI Picks with a `model_training` icon. There is no model.

### Frontend panels

| Panel | Status | Detail |
|---|---|---|
| Chart | **STUB** | `lightweight-charts` candlestick + volume, wired to `/api/history`. Renders correctly for `^NSEI` and `BTC` (verified, real OHLCV). Broken for every US equity: `routes.py:278` rewrites any symbol without `.` or `^` to `SYMBOL.NS`, so `AAPL` is fetched as `AAPL.NS`. Verified: `GET /api/history?symbol=AAPL&timeframe=1D` → `{"data":[]}` → blank chart, no error state. `/api/details?symbol=AAPL` → every field `0` for the same reason. `get_history` also has no `return` on its exception path (`routes.py:306-307`), so a fetch failure returns `null` and the chart silently renders nothing. |
| Order book | **ABSENT** | No bid/ask/depth component, no endpoint, no provider that supplies L2. Nothing to render. |
| Watchlist | **STUB** | `/watchlist` page reads `watchlistData.symbols` (`watchlist/page.tsx:553`); the backend returns `{"watchlist": [...]}` (`routes.py:349`). The table body is therefore **always empty**, and the empty-state row never shows either because `undefined?.length === 0` is false. Even on a key match, the backend attaches no quote data, so Price/Change/Volume would be `---`. The rows carry a random sparkline (§2). |
| Backtest UI | **ABSENT** | No page, no route, no nav entry. |
| Paper portfolio | **STUB** | Every fetch targets a URL that does not exist. Frontend calls `/api/paper-portfolio/{id}`, `/api/paper-trades/{id}`, `/api/paper-trades/{id}/close`; the app serves `/api/paper/portfolio`, `/api/paper/trades`, and `DELETE /api/paper/trades/{id}` (verified against the generated OpenAPI). All 404. Field names are also mismatched independently of the URLs (`cash_balance`/`total_value`/`total_pnl` vs `virtual_balance`/`total_realized_pnl`; `trades.trades` vs `{open_trades, closed_trades}`), and status casing differs (`'OPEN'` vs `'open'`). The page still renders `$100,000.00` equity and a 30-point equity curve — both invented client-side (§2). |
| Symbol detail | **STUB** | Quote panel calls `/api/market_data/quote/{market}/{ticker}` — **that endpoint does not exist anywhere in the backend.** Price, change, and the whole trade-risk preview render from `undefined`. "Get AI Analysis" is a `setTimeout` (§2). |
| AI Picks | **STUB** | Calls a real endpoint that returns nothing. Verified: `POST /api/picks {market:"US"}` → `{"picks":[]}`. Cause: the agent returns `entry_zone: "140-150"` (a range string), `routes.py:201` does `float(data.get("entry_zone", 100))`, `ValueError`, per-ticker `except` swallows it, list stays empty. The table renders zero rows with no empty state and no error. |
| Events | **WORKING** (feed) / **STUB** (impact) | `GET /api/events` returns live Finnhub headlines — verified. But `severity` is a substring hack: `"High" if "rate" or "fed" in headline else "Medium"` (`routes.py:104`), and `timestamp` is the literal string `"Recent"`. The drill-down is a live LLM call (verified, returns real prose) whose `severity` is **pinned to `"High"` in the prompt template itself** (`routes.py:148`) and whose beneficiary/pressure tickers are unvalidated LLM output. |
| Nav | broken links | Sidebar links to `/paper/history`, `/scanner`, `/health` — none of these pages exist. Watchlist badge is hardcoded `3`. |
| Navbar ticker strip | **STUB** | `<TickerItem {...t} />` destructures a `ticker` prop; the backend quote objects use `symbol`. Every ticker in the scrolling strip renders with a blank name next to a real price. |

Root `dashboard.html`, `watchlist.html`, `stock_picks.html`, `event_drill_down.html` are static Tailwind-CDN design mockups with no fetch calls. Dead weight, superseded by `frontend/`.

### Tests — **ABSENT**

Zero test files of any kind: no pytest, no jest/vitest, no Playwright, no `conftest.py`, no CI config. `implementation_plan.md` explicitly declares "Automated Tests: N/A - Reliance on runtime logs". There is also no `requirements.txt` or `pyproject.toml` in `backend/` — the dependency set exists only inside the committed `venv/`, so the backend is not reproducibly installable.

---

## 2. Hardcoded / random / mock data that renders as if real

Ranked by how likely a user is to act on the fake value.

1. **`Math.random()` price sparklines shown as market data.** `watchlist/page.tsx:496` and `picks/page.tsx:263`. In Picks the column is literally headed **"Projection"** and is rendered inside a row containing a real ticker, a real-looking entry, target, stop, and a confidence bar. The line's direction is seeded by the LLM's verdict, so it always agrees with the recommendation. This is a fabricated forecast presented next to a trade instruction. It regenerates on every render.
2. **Fabricated price levels from the LLM, presented as a trade setup.** `/api/picks` asks the model for entry/target/stop with **no live price in the prompt** — `stock_analysis_agent` has a `get_live_price` tool but nothing forces its use. Verified output for AAPL: `entry_zone "140-150", target "170", stop_loss "130"` while AAPL was trading at **327.49**. When the parse succeeds, those numbers reach the UI as an actionable setup, and `picks/page.tsx` pipes them straight into the Simulate Trade dialog. `routes.py:201-203` also has silent fallbacks `entry=100, target=120, stop=90` — pure placeholders that would render as a real setup.
3. **Random 30-day equity curve on the Paper Portfolio page.** `paper/page.tsx:11-25` — `val += (Math.random() - 0.45) * 500`, drawn under the heading "Performance History". The `-0.45` bias makes it trend up. It ignores the portfolio API entirely and is not even labelled as sample data. Alongside it, `$100,000.00` equity and `0.00` PnL are hardcoded fallbacks (`paper/page.tsx:62,90`) that display identically whether the backend is healthy or 404ing — which it currently is.
4. **The "AI Analysis" button on the symbol page is a `setTimeout` with a canned paragraph.** `symbol/[ticker]/page.tsx:160-167`. It waits 2.5s to simulate thinking, then prints prewritten text asserting a "strong support zone near recent lows" and **"RSI is neutral at 48"** — a specific technical indicator value that is invented and constant for every symbol. The only real number interpolated is `price * 1.03`.
5. **Zeroed change on every websocket-sourced US quote.** `finnhub_ws.py:63-72` caches `change: 0.0, change_percent: 0.0` next to a live price, and `MarketDataService` prefers that cache. A stock down 4% renders as `+0.00 (0.00%)` in green (`change >= 0` is true for 0).
6. **`sentiment_score = 100 - vix*2`**, `routes.py:80`, commented "rough inverse correlation". An invented formula surfaced as a market sentiment metric.
7. **Silent fake fallbacks in `/api/dashboard`.** Bare `except:` blocks substitute `vix = 14.2` (`routes.py:43`), `IT +1.2% / Banking -0.8%` sector momentum (`routes.py:55-58`), and a fabricated `"US Fed Interest Rate Decision"` event (`routes.py:73`). These are indistinguishable from live data downstream; the dashboard renders them into the sector-momentum bar chart and the "Live Macro Events" table.
8. **Hardcoded provenance strings in the events table.** `dashboard/page.tsx:157,164` renders Time = `"Just now"` and Source = `"AI Macro Engine"` for every row, regardless of the real Finnhub source and publication time that the API returns.
9. **`MOCK_SYMBOLS`** (`routes.py:215`) is served from `/api/symbols/search` whenever Finnhub fails, with no marker. Also `MOCK_USER_SESSION = "mock_session_user_1"` is the single global identity for all watchlist and paper-trading state — there is no per-user isolation despite Supabase Auth being wired up in the frontend.
10. **Mock agent tools feeding a live alert path.** `alert_monitoring.py` returns `"New macro event: RBI announces unexpected rate cut."` from `scan_macro_feed()`. This agent is invoked by the real anomaly detector on a real price move (`anomaly.py:62`); the LLM's alert decision is therefore reasoning over a fixed fiction. (Currently harmless only because its output is logged and never shown — see the dead-code note below.)

Dead-but-fake, for completeness: `anomaly.py`'s `active_flags` list is appended to but never read by any endpoint, and `/api/alerts` returns a hardcoded `{"alerts": []}` (`routes.py:379`). The circuit-breaker branch only triggers for `^NSEI`/`NIFTY`, which are never passed to `check_tick()` by either the poller or the websocket — so that whole block is unreachable.

---

## 3. Backtest path — future information

**There is no backtest.** No lookahead bug can exist in code that does not exist. What follows are the places where the same class of error is already present, or is guaranteed to appear the moment a backtest is written on top of this data layer.

1. **`/api/history` returns the current, still-forming candle.** `routes.py:288` calls `yf.history(period, interval)` and emits every row unfiltered, including today's partial bar for `1D`/`1W` and the in-progress bar for intraday. Any strategy evaluated on the last bar of this series reads a high/low/close that has not finished happening. This is the single most likely source of future leakage in anything built here.
2. **Settlement resolves target before stop on the same tick, and the tick is up to 60s stale.** `settlement.py:47-56` polls every 20s and checks `current_price >= target` first, `<= stop` second. Between two polls a bar can trade through both levels; the code unconditionally awards the profitable exit. Worse, the price it compares against comes from `MarketDataService.get_quote`, which serves a **60-second Redis cache** (`service.py:77`) — so a "fill" can be booked against a price observed up to a minute before or after the actual crossing, with no bar data to adjudicate. Fills are also assumed to occur exactly at the target/stop level: no slippage, no gap handling, no spread, no fees.
3. **Entry price is client-supplied and unvalidated.** `POST /api/paper/trades` accepts `entry_price` from the browser (`api/paper.py:14-22`) and never checks it against a live quote. `picks/page.tsx:299` passes the LLM's invented entry (see §2.2), so a position can be opened at a price the asset never traded at — after the fact. That is retroactive fill selection, which is the trading-simulation equivalent of lookahead.
4. **Manual close computes no PnL at all.** `DELETE /api/paper/trades/{id}` sets `status = closed_manual` and stamps `closed_at`, but never fetches an exit price and never writes `realized_pnl` (`api/paper.py:127-130`). The trade keeps `realized_pnl = 0.00`. `GET /api/paper/portfolio` then counts every manually closed trade as a non-win in its win-rate denominator (`api/paper.py:50`), permanently biasing the reported win rate downward. In-memory closes never touch the portfolio balance either.
5. **In-memory trades are never settled.** The APScheduler settlement job returns immediately when Supabase is unreachable (`settlement.py:11-15`) — which is the current state. Trades opened via the in-memory fallback path sit open forever and are invisible to settlement. The 20s job is running and doing nothing on every tick.
6. **News context has no as-of boundary.** `search_recent_company_news` (`stock_analysis.py:425`) always queries `now - 7 days → now`. There is no point-in-time parameter anywhere in the data layer, so a historical simulation using these agents would feed the model news published after the simulated decision date. The infrastructure to avoid this does not exist.

---

## 4. Dependencies installed but unused

**Frontend** (`frontend/package.json`, cross-checked against every import in `src/`):

| Package | Status |
|---|---|
| `@radix-ui/react-dropdown-menu` | never imported |
| `@radix-ui/react-tabs` | never imported — the Paper page hand-rolls tabs with `useState` |
| `@radix-ui/react-tooltip` | never imported |
| `@tsparticles/react` | never imported |
| `tsparticles` | never imported |
| `zustand` | never imported — all state is `useState` + react-query |
| `zod` | never imported — **no runtime validation exists anywhere**, which is why the API/UI field mismatches in §1 fail silently |
| `date-fns` | never imported |
| `clsx` | never imported — class strings are template literals |
| `tailwind-merge` | never imported |

Used: `next`, `react`, `react-dom`, `@tanstack/react-query`, `@supabase/supabase-js`, `lightweight-charts`, `recharts`, `framer-motion`, `react-hot-toast`, `@radix-ui/react-dialog`, `next-pwa` (via `next.config.ts`), `tailwindcss`.

**Backend** — there is no manifest to audit against; the venv is the manifest. Directly imported: `fastapi`, `slowapi`, `pydantic`, `pydantic-settings`, `httpx`, `redis`, `yfinance`, `websockets`, `apscheduler`, `supabase`, `openai`, `google-genai`, `uvicorn`.

- `google-genai` — imported at module load in `services/llm/provider.py:145`, but `GEMINI_API_KEY` is empty in both `.env` and the config default, so `self.gemini_client` is always `None` and every Gemini branch is unreachable. A ~50MB dependency tree (`google-auth`, `protobuf`, `pyasn1`) carried for dead code.
- `numpy`, `pandas`, `beautifulsoup4`, `peewee`, `curl_cffi`, `multitasking`, `pytz` — transitive `yfinance` deps, not imported by project code. Listed because their presence is what makes this venv look like it contains an analytics stack. It does not.
- `cryptography`, `pyjwt`, `rich`, `pygments`, `tenacity`, `tqdm` — transitive only.

---

## 5. Also worth stating plainly

**Live credentials are committed in source, twice.** `backend/core/config.py:6-30` carries working Groq, Alpha Vantage, Finnhub, and CoinGecko keys, an Upstash Redis token, and a **Supabase `service_role` JWT** — as *default values in the settings class*, not just in `.env`. `backend/.env.example` contains the same real secrets. The service-role key bypasses all row-level security. It decodes to `exp` 2036. Even though that Supabase host no longer resolves, these keys should be treated as burned and rotated. `backend/` is not under version control (only `frontend/` is a git repo, one commit, "Initial commit from Create Next App"), which is the only reason they haven't been pushed anywhere yet.

**Config loading is CWD-dependent.** `model_config = SettingsConfigDict(env_file=".env")` resolves relative to the process working directory. Launched from the repo root instead of `backend/`, `.env` is not found and the hardcoded defaults take over — including `LLM_PROVIDER_PRIMARY = "ollama"`, which then fails to a Groq fallback on every single LLM call. Verified: primary provider errored, fallback returned `OK`.

**`except:` / `except Exception:` with no re-raise is the dominant error-handling pattern** — 20+ sites. Every one of them converts a failure into plausible-looking data with an HTTP 200. That is the mechanism by which most of §2 reaches the screen.

---

## Summary table

| Item | Classification |
|---|---|
| Exchange ingestion / websocket | STUB |
| Database schema & persistence | STUB (nothing persists; host unreachable) |
| Backtesting | ABSENT |
| ML / forecasting | ABSENT (LLM prompting only) |
| Frontend — chart | STUB (works for indices/crypto, broken for US equities) |
| Frontend — order book | ABSENT |
| Frontend — watchlist | STUB (renders empty; key mismatch) |
| Frontend — backtest UI | ABSENT |
| Frontend — paper portfolio | STUB (all endpoints 404) |
| Frontend — AI picks | STUB (always empty; parse failure) |
| Frontend — events feed | WORKING (feed) / STUB (impact, severity faked) |
| Tests | ABSENT |
