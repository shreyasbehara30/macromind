# MacroMind — AI-Agentic Macro-Event Analyzer & Stock Intelligence Dashboard

CSE mini project (Team E5) at Geethanjali College of Engineering and Technology (GCET),
guide Dr. B. Mamtha. Covers NSE, US, and crypto: live quotes, charts, fundamentals,
an LLM event pipeline, watchlist, paper trading, and a backtesting lab.
A research/education dashboard — it never places real orders.

## Features

- **Dashboard** — live index/crypto tickers, sector momentum, macro-events table, global 8-market board, chart with timeframe switching and one-click **Trade** jump.
- **Live Events** — real Finnhub news feed with LLM severity classification, full impact analysis (chain reaction, beneficiary/pressure stocks with market-aware links), plus a live market pulse refreshing every 5s.
- **AI Picks** — trade setups whose levels are grounded in the live quote and validated against a fixed 20% deviation band.
- **Watchlist** — Supabase-persisted (local SQLite fallback), hydrated with live quotes, idempotent on duplicates.
- **Paper Portfolio** — virtual $100k account, live marks with unrealized P&L, auto-settlement on target/stop, manual close booked at the live mark with realized P&L, one-click reset, and a trade ticket with mini-chart.
- **Backtest Lab** — MA-crossover vs buy-and-hold on 5 years of closed candles (forming bar dropped, next-close execution, costs charged), Monte Carlo fan chart, statistical projection bands, top-of-book depth.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, TypeScript strict, Tailwind, lightweight-charts, react-query |
| Backend | FastAPI, Python 3.14, uvicorn |
| LLM | Groq (`GROQ_MODEL`, default `openai/gpt-oss-120b`), Gemini fallback |
| Market data | yfinance (equities), CoinGecko (crypto), Finnhub (news/quotes), AlphaVantage (US fallback) |
| Persistence | Supabase (PostgreSQL) when reachable, otherwise local SQLite (`backend/data/`, gitignored) |

## Quickstart

```bash
# 1. Backend
cd backend
cp .env.example .env   # then fill in keys (never commit .env)
pip install -r requirements.txt
python -m uvicorn main:app --port 8000   # docs at /docs

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev -- --port 3001   # :3000 if free; backend CORS allows 3000-3002
```

Open `http://127.0.0.1:3001` (or `localhost:3001`). Sign in with any email —
demo auth falls back to a stable per-email local session when Supabase Auth is
unreachable. Finnhub search needs a live key; without it search/events go empty
and US quotes fail over to AlphaVantage/yfinance.

## Environment

All secrets come from `backend/.env` (see `backend/.env.example` for the full
list with placeholders — no real values are committed anywhere). Required for
full functionality: `GROQ_API_KEY`, `FINNHUB_API_KEY`. Optional with graceful
degradation: `GEMINI_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `SUPABASE_URL` +
`SUPABASE_SERVICE_ROLE_KEY` (falls back to local SQLite), Upstash Redis
(in-memory TTL cache covers for it).

## API cheat sheet

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness |
| GET | `/api/dashboard` · `/api/global` | Tickers, sectors, events / world board |
| GET | `/api/events` · `/api/events/{id}/impact` | Classified feed · impact analysis |
| POST | `/api/picks` | Grounded AI trade setups |
| GET/POST/DELETE | `/api/watchlist…` | Persisted watchlist |
| GET/POST/DELETE | `/api/paper/…` | Portfolio, trades, live-mark close, reset |
| POST | `/api/backtest` · `/api/backtest/montecarlo` | Strategy backtest · GBM fan |
| GET | `/api/backtest/projection` · `/api/backtest/depth` | Statistical bands · top-of-book |
| GET | `/api/history` · `/api/details` · `/api/market_data/quote/{m}/{t}` | Charts, fundamentals, quotes |
| GET | `/api/alerts` · `/api/portfolio/impact` | Anomaly flags · holdings impact |

## Testing

```bash
cd backend && venv/Scripts/python -m pytest -q   # 60+ tests incl. frontend-backend contract test
cd frontend && npx tsc --noEmit
```

The contract test parses `frontend/src/lib/api.ts` and asserts every call
resolves against the live backend route table — keep all API calls in that file.

## Honesty notes (read before the review)

- Demo auth accepts any credentials; per-user isolation is via `X-Session-Id`.
- Projection/Monte Carlo are statistics, labelled as such — there is no trained forecasting model.
- Depth is best bid/ask only; no full order-book ladder exists in the free feeds.
- Paper trading is simulated; closes book against live marks, never real fills.
- If Supabase is unreachable the app persists locally instead of failing.

## Layout

```
backend/   FastAPI (api/, core/, services/agents|events|market_data|paper_trading|realtime|backtest/, tests/)
frontend/  Next.js (app/, components/, lib/api.ts = the only API client, lib/session.ts)
```

Team: Shreyas Behara (23R11A05N0), Saketh Nara (24R15A0523), G. Akhil (23R11A05K7).
