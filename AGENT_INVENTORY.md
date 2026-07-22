# AGENT_INVENTORY.md

Date: 2026-07-22. Scope: every agent, agent-like class, and LLM tool under `backend/`. Traced from source and call sites, not from prior audits. Line numbers are current.

## Infrastructure (not agents themselves)

- **`services/agents/runner.py` — `AgentRunner`.** Base class. Runs a tool-calling loop (max 6 iterations) over `llm_provider`, executing any tool the model calls and feeding the result back. All four agents subclass it. Passes `self.tools` to the LLM on every call even when the prompt says "do not call tools." Also accepts a `context_augmentation` string that nothing currently passes (see `context_assembler`).
- **`services/llm/provider.py` — `LLMProvider`.** Wraps Groq / Gemini / Ollama behind one `generate()`. Config: `LLM_PROVIDER_PRIMARY=groq`, fallback `groq` (`core/config.py:22-23`, `.env:4`). Gemini client is `None` (no key), so Gemini branches are unreachable.

---

## Agents

### 1. `stock_analysis_agent` — `services/agents/stock_analysis.py:78` → **LIVE**

- **Claims:** produce buy/sell/hold verdict with confidence, entry zone, target, stop-loss for a ticker.
- **Live path:** `POST /api/picks` → `api/routes.py:220` `await stock_analysis_agent.run(prompt)`. Output is parsed, validated against the live quote (20% band), and returned in `{"picks": [...]}`, which `frontend/src/app/picks/page.tsx:18` (`fetchPicks`) renders as the picks table. **Reaches the user.**
- **LLM:** yes, via `AgentRunner` → `llm_provider`.
- **Tools — all return real data:**
  - `get_live_price(symbol, market)` → `market_data_service.get_quote` — real.
  - `get_sector_momentum(sector)` → yfinance sector ETF — real.
  - `search_recent_company_news(symbol)` → Finnhub company-news — real.
  - `get_macro_signals()` → yfinance `^VIX` — real.
- **Note:** the `/picks` prompt instructs the model *not* to call tools, and grounds it with the live price inline instead (`routes.py`, item 5 work). So in practice the verdict is produced without exercising these four tools, even though they are real and offered. Output rendered.

### 2. `macro_research_agent` — `services/agents/macro_research.py:41` → **LIVE** (one path renders, one discards)

- **Claims:** autonomously research a macroeconomic event and produce a briefing.
- **Call site A — LIVE:** `GET /api/events/{id}/impact` → `api/routes.py:151` `await macro_research_agent.run(prompt)`. The prompt asks for a fixed JSON shape (title/severity/ai_analysis/chain_reaction/stocks); the response is regex-extracted, parsed, and returned. Rendered by both `frontend/src/app/events/page.tsx:112,148` and `frontend/src/app/events/[id]/page.tsx:67,80,106` (`ai_analysis`, `chain_reaction`, `stocks.beneficiaries/pressure`). **Reaches the user.**
- **Call site B — LOGGED/discarded:** `PollingService.poll_news` → `services/realtime/polling.py:76` `await macro_research_agent.run(task)`. The return value is **not captured** — the call is awaited and thrown away. Runs every 5 minutes (`NEWS_POLL_INTERVAL_HIGH_PRIORITY=300`) as a background job. Produces nothing a user sees; not even logged.
- **LLM:** yes.
- **Tools — return real data:**
  - `search_news(query)` → Finnhub general news, naive substring filter — real.
  - `fetch_rbi_fed_documents(entity)` → delegates to `search_news(f"{entity} rate interest inflation")`. Real news, but mislabeled: it does not fetch RBI/Fed documents, it runs a keyword news search. Real data, misleading name.
- **Note:** on call site A the prompt says "DO NOT call any tools," so the briefing is typically the model's own output with no tool grounding. The former canned tool `get_historical_analogues` was removed in an earlier session — confirmed absent.

### 3. `alert_monitoring_agent` — `services/agents/alert_monitoring.py:20` → **LOGGED**

- **Claims:** judge whether a new event is significant enough to push a notification, output a JSON decision.
- **Runs on a live background path, but output goes nowhere:** `services/realtime/anomaly.py:62` `decision = await alert_monitoring_agent.run(task)`, called from `_trigger_alert_agent` (`anomaly.py:56`), fired by `check_tick` (`anomaly.py:51`) when a symbol moves ≥1.5% in the rolling window. `check_tick` is fed **real ticks** — `finnhub_ws.py:59` (live trades) and `polling.py:66` (real 20s quotes). So the agent genuinely fires on real market moves. But `decision` is only `logger.info`'d (`anomaly.py:63`); no endpoint returns it and no UI reads it.
- **LLM:** yes — but it reasons over **canned tool data.**
- **Tools — both CANNED:**
  - `scan_macro_feed()` → returns the fixed string `"New macro event: RBI announces unexpected rate cut."` regardless of input.
  - `check_watchlist_relevance(event, watchlist)` → fixed f-string asserting relevance to "banking stocks."
- **So even though the trigger is real, the LLM's alert judgment is grounded in fiction, and the judgment is discarded anyway.**
- **Related dead output:** `AnomalyWatcher.active_flags` (circuit-breaker warnings, `anomaly.py:44`) is appended but never read. The circuit-breaker branch only fires for `symbol in ["^NSEI","NIFTY"]` (`anomaly.py`), and neither poller feeds those symbols (`polling.py` watches RELIANCE.NS/TCS.NS/BTC/ETH; `finnhub_ws.py` watches BTCUSDT/AAPL/MSFT/TSLA/NVDA), so the branch is unreachable. `GET /api/alerts` returns hardcoded `{"alerts": []}` (`routes.py:490`).

### 4. `portfolio_impact_agent` — `services/agents/portfolio_impact.py:23` → **DEAD**

- **Claims:** given holdings and active macro events, return position-specific impact assessments.
- **Never invoked.** Imported at `api/routes.py:8` and never used — `.run()` is called nowhere in the repo (grep for `portfolio_impact` returns only the import). The import is the sole reference.
- **LLM:** would call it if invoked, but it isn't.
- **Tools — all CANNED (moot):** `get_user_holdings` (fixed holdings string), `get_active_macro_events` (fixed events string), `assess_position_risk` (fixed risk f-string).

---

## The three flagged orphans

### `services/events/classifier.py` — `EventClassifier` / `event_classifier:48` → **DEAD, real implementation**

- **Real?** Yes. `classify_headline(headline)` calls `llm_provider.generate(..., response_schema=ClassifiedEvent)` and parses into a Pydantic model (`event_type`, `severity`, `affected_asset_classes`, `affected_sectors`, `summary`), with a Low-severity fallback on failure. It is a complete, functional LLM classifier.
- **Invoked?** No. `classify_headline` is called from nowhere. The only external reference to this file is `impact.py` importing the **`ClassifiedEvent` model** (not the classifier instance).
- **Wiring required:** call `event_classifier.classify_headline(headline)` where structured severity is needed — most naturally inside `GET /api/events` (which currently emits `severity: None` for every headline) or at the top of `/events/{id}/impact`. Cost: one LLM call per headline; on the events list that is N calls per page load, with latency and rate-limit exposure. No schema change needed on its own.

### `services/events/impact.py` — `ImpactMappingEngine` / `impact_mapping_engine:51` → **DEAD, real implementation, and a duplicate of the live feature**

- **Real?** Yes. `map_impact(event: ClassifiedEvent, current_prices)` calls the LLM with `response_schema=EventImpact` and returns structured `chain_reaction: [{step, description}]` + `stocks: [{ticker, name, market, impact, reasoning}]`, empty-list fallback on failure.
- **Invoked?** No. `map_impact` is called nowhere.
- **Critical point:** the **live** impact feature (`/events/{id}/impact`) does **not** use this engine. It hand-rolls an inline prompt through `macro_research_agent` (agent #2, call site A) and returns a *different* JSON shape. So this file is a second, better-structured impact implementation sitting unused next to the one that actually ships.
- **Wiring required, and it is not a drop-in:**
  1. It needs a `ClassifiedEvent` input, so `classifier.py` must be wired first.
  2. Its output shape differs from what the frontend consumes. Frontend expects `chain_reaction: string[]` and `stocks: {beneficiaries[], pressure[]}` (`events/page.tsx:148`, `events/[id]/page.tsx:80,106`). This engine emits `chain_reaction: [{step, description}]` and a flat `stocks[]` with an `impact` discriminator field. Wiring means either an adapter in the route or a frontend change.
  3. `current_prices` must be assembled and passed.

### `services/agents/context_assembler.py` — `ContextAssembler` / `context_assembler:45` → **DEAD, real implementation, no LLM**

- **Real?** Yes, though trivial and pure-Python (no LLM). `retrieve_and_rank(raw_events, prices)` filters to High/Medium severity events; `augment(context_data)` formats them into a `<live_data>/<macro_events>` delimited block — i.e. the "RAG" context string.
- **Invoked?** No. Nothing imports `context_assembler`. Notably, `AgentRunner.run` already has a `context_augmentation` parameter (`runner.py:12`) designed to receive exactly this string, but no caller ever passes it.
- **Wiring required:** build events+prices, call `retrieve_and_rank` then `augment`, and pass the result as `agent.run(message, context_augmentation=...)`. **Blocked by a data gap:** `retrieve_and_rank` keeps only events whose `severity` is "high"/"medium", but `/api/events` now emits `severity: None` for everything (severity keyword-hack was removed). So without `classifier.py` populating severity first, this filter discards every event and the augmented block is empty. Wiring it usefully depends on wiring the classifier.

**These three form a coherent, unused pipeline** — classify → assemble context → map impact — that was built but never connected. The shipping event-impact feature bypasses all three in favor of one inline `macro_research_agent` prompt.

---

## Summary

| Component | File | Classification | LLM? | Tools real? | Output destination |
|---|---|---|---|---|---|
| `stock_analysis_agent` | agents/stock_analysis.py | **LIVE** | yes | yes (4/4) | picks table |
| `macro_research_agent` (impact) | agents/macro_research.py | **LIVE** | yes | yes (2/2) | events UI |
| `macro_research_agent` (news poll) | realtime/polling.py:76 | **LOGGED** (discarded) | yes | yes | return value thrown away |
| `alert_monitoring_agent` | agents/alert_monitoring.py | **LOGGED** | yes | **canned (2/2)** | `logger.info` only |
| `portfolio_impact_agent` | agents/portfolio_impact.py | **DEAD** | n/a | canned (3/3) | never invoked |
| `event_classifier` | events/classifier.py | **DEAD** | yes | n/a | never invoked |
| `impact_mapping_engine` | events/impact.py | **DEAD** | yes | n/a | never invoked |
| `context_assembler` | agents/context_assembler.py | **DEAD** | no | n/a | never invoked |

- **2 agents reach the user** (`stock_analysis`, `macro_research` via impact).
- **1 agent fires on real market moves but its output is only logged** (`alert_monitoring`), and it reasons over canned tool data.
- **1 agent invocation is a background job whose result is discarded** (`macro_research` news poll).
- **4 classes are dead** (`portfolio_impact_agent`, and the classifier→context→impact trio), three of which are genuine implementations, not stubs.
- **Canned tools live in exactly two agents:** `alert_monitoring` (both tools) and `portfolio_impact` (all three). Every tool in the two live agents returns real data.
