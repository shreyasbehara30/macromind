# MacroMind Additions: Latency Reduction & Paper Trading Platform

This plan outlines the implementation of a free-tier real-time latency reduction layer and a new paper trading risk-practice platform.

## Goal Description
1. **Addition 1**: Introduce a latency reduction layer (`services/realtime/`) utilizing Finnhub websockets for sub-second US ticker updates, while tightening polling intervals for Indian/Crypto assets to 20s and high-priority news to 5m. Add a lightweight, zero-LLM `AnomalyWatcher` to detect 1.5% rolling window deviations and circuit breakers to instantly trigger out-of-cycle AI alerts.
2. **Addition 2**: Introduce Layer 6 for Paper Trading. Adds Supabase schema to track simulated trades and a virtual portfolio. Includes an APScheduler job for background trade settlement and a new frontend `/paper` screen to view open/closed simulated trades. Connects directly to AI Stock Picks with a "Simulate this pick" button.

## User Review Required

> [!WARNING]
> **Dependencies**: The backend will require `websockets` for the Finnhub feed, `apscheduler` for background polling/settlement loops, and `supabase` client for the paper trading tables.
> **Supabase Migrations**: Since we don't have a configured migration runner, I will provide the raw SQL for `paper_trades` and `paper_portfolio` tables. You will need to execute this SQL in your Supabase dashboard. Is this acceptable?

## Proposed Changes

---

### Backend Configuration

#### [MODIFY] [config.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/core/config.py)
- Add variables: `FINNHUB_WEBSOCKET_ENABLED`, `ANOMALY_THRESHOLD_PERCENT`, `ANOMALY_WINDOW_MINUTES`, `NEWS_POLL_INTERVAL_HIGH_PRIORITY`.

#### [MODIFY] [.env.example](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/.env.example)
- Add the new settings variables.

---

### Layer 1.5: Realtime Engine & Anomaly Watcher

#### [NEW] [services/realtime/finnhub_ws.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/services/realtime/finnhub_ws.py)
- Finnhub websocket client to subscribe to US watchlisted tickers. Pushes latest ticks to Redis. Triggers `AnomalyWatcher.check_tick()`.

#### [NEW] [services/realtime/polling.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/services/realtime/polling.py)
- APScheduler jobs for tight 20s polling on non-WS tickers (NSE, Crypto) and 5m polling on priority news. 

#### [NEW] [services/realtime/anomaly.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/services/realtime/anomaly.py)
- Pure Python logic to check for >1.5% deviations in 5 mins using Redis sliding windows, and hardcoded NSE circuit breaker limits. Dispatches to Alert Monitoring agent.

#### [MODIFY] [main.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/main.py)
- Hook the WebSocket runner and APScheduler start/shutdown into FastAPI's `lifespan` manager.

---

### Layer 6: Paper Trading

#### [NEW] [services/paper_trading/schema.sql](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/services/paper_trading/schema.sql)
- Supabase SQL schema definitions for `paper_trades` and `paper_portfolio` tracking virtual cash balance and realized PnL.

#### [NEW] [services/paper_trading/settlement.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/services/paper_trading/settlement.py)
- APScheduler task running on the 20s cycle to fetch active paper trades, compare against `MarketDataService` prices, and auto-close on target or stop-loss.

#### [NEW] [api/paper.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/api/paper.py)
- REST endpoints for paper trading (`POST /api/paper-trades`, `GET /api/paper-trades`, `DELETE /api/paper-trades/{id}`, `GET /api/paper-portfolio`).

#### [MODIFY] [api/routes.py](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/backend/api/routes.py)
- Register `api/paper.py` router.

---

### Frontend Screens

#### [NEW] [src/app/paper/page.tsx](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/frontend/src/app/paper/page.tsx)
- New screen with header stats (Virtual Balance, P&L, Win Rate), Open Positions list, and Closed History list.
- Contains the mandatory disclaimer: "Simulated trading with virtual funds — no real money is used or at risk. For educational and risk-practice purposes only."

#### [MODIFY] [src/app/picks/page.tsx](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/frontend/src/app/picks/page.tsx)
- Add the "Simulate this pick" button which auto-populates a POST request to open a paper trade based on AI parameters.

#### [MODIFY] [src/app/layout.tsx](file:///c:/Users/ECHO/OneDrive/Desktop/fintech/frontend/src/app/layout.tsx)
- Add "Paper Portfolio" to the sidebar navigation.

## Verification Plan
### Automated Tests
- N/A - Reliance on runtime logs for websocket connection stability.
### Manual Verification
- Deploy backend and monitor the APScheduler logs to ensure 20s polling and settlement sweeps are functioning.
- Submit a paper trade from the frontend, then manually override the mock current price in Redis to force a take-profit hit, ensuring settlement automatically updates the portfolio balance.
