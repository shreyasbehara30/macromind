/**
 * The only place in the frontend that knows API URLs.
 *
 * Every request goes through here so that:
 *  - paths exist in exactly one file, checkable against the backend route table
 *    (see backend/tests/test_api_contract.py)
 *  - response and request shapes are typed, so reading a key the API does not
 *    return is a compile error rather than a silent `undefined` on screen
 *
 * Do not call fetch() against the API directly from a component.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Market = "NSE" | "BSE" | "US" | "CRYPTO" | "COMMODITY" | "FOREX";

export interface Quote {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  currency: string;
  currency_symbol: string;
  market: Market;
  timestamp: string;
  source: string;
  error: string | null;
}

export interface SectorMomentum {
  sector: string;
  change: number;
}

export interface TopEvent {
  id: string;
  title: string;
  severity: string | null;
}

export interface DashboardResponse {
  tickers: Quote[];
  sector_momentum: SectorMomentum[];
  top_events: TopEvent[];
}

export interface MacroEvent {
  id: string;
  severity: string | null;
  headline: string;
  source: string;
  timestamp: string | null;
  sectors: string[];
}

export interface EventsResponse {
  events: MacroEvent[];
  page: number;
  total: number;
}

export interface ImpactStock {
  ticker: string;
  reason: string;
}

export interface EventImpactResponse {
  title: string;
  severity: string | null;
  ai_analysis: string | null;
  chain_reaction: string[];
  stocks: {
    beneficiaries: ImpactStock[];
    pressure: ImpactStock[];
  };
}

export interface Pick {
  ticker: string;
  market: Market;
  side: "LONG" | "SHORT";
  entry_low: number;
  entry_high: number;
  target: number;
  stop_loss: number;
  confidence: number;
  reason: string | null;
  event: string | null;
}

export interface PicksResponse {
  picks: Pick[];
}

export interface SymbolSearchResult {
  ticker: string;
  name: string;
  /** null when the registry has no entry: unknown, and never defaulted to US. */
  market: Market | null;
  type: string;
}

export interface SymbolSearchResponse {
  symbols: SymbolSearchResult[];
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  value: number;
}

export interface HistoryResponse {
  data: Candle[];
}

export interface DetailsResponse {
  open: number;
  dayHigh: number;
  dayLow: number;
  volume: number;
  fiftyTwoWeekHigh: number;
  fiftyTwoWeekLow: number;
  marketCap: number;
  peRatio: number;
  dividendYield: number;
  sector: string;
  longName: string;
}

export interface WatchlistItem {
  ticker: string;
  market: Market;
}

export interface WatchlistResponse {
  watchlist: WatchlistItem[];
}

export interface PaperPortfolioResponse {
  virtual_balance: number;
  total_realized_pnl: number;
  win_rate: number;
  avg_pnl: number;
}

export interface PaperTrade {
  id: string;
  ticker: string;
  market: Market;
  direction: "LONG" | "SHORT";
  entry_price: number;
  quantity: number;
  target_price: number | null;
  stop_loss_price: number | null;
  status: "open" | "closed_target" | "closed_stoploss" | "closed_manual";
  opened_at: string;
  closed_at: string | null;
  realized_pnl: number | null;
  source: string | null;
}

export interface PaperTradesResponse {
  open_trades: PaperTrade[];
  closed_trades: PaperTrade[];
}

/** Mirrors backend PaperTradeCreate. Field names must match the Pydantic model. */
export interface PaperTradeCreate {
  ticker: string;
  market: Market;
  direction: "LONG" | "SHORT";
  quantity: number;
  entry_price: number;
  target_price?: number | null;
  stop_loss_price?: number | null;
  source?: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // response body was not JSON; keep the status-based message
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

// --- routes -----------------------------------------------------------------
// Keep these template strings literal. The contract test parses this file.

export const fetchDashboard = () => request<DashboardResponse>(`/api/dashboard`);

export const fetchEvents = (page = 1, limit = 10) =>
  request<EventsResponse>(`/api/events?page=${page}&limit=${limit}`);

export const fetchEventImpact = (id: string) =>
  request<EventImpactResponse>(`/api/events/${id}/impact`);

export const fetchPicks = (market: string, horizon: string) =>
  request<PicksResponse>(`/api/picks`, {
    method: "POST",
    body: JSON.stringify({ market, horizon }),
  });

export const searchSymbols = (q: string) =>
  request<SymbolSearchResponse>(`/api/symbols/search?q=${encodeURIComponent(q)}`);

export const fetchHistory = (symbol: string, market: Market | string, timeframe: string) =>
  request<HistoryResponse>(
    `/api/history?symbol=${encodeURIComponent(symbol)}&market=${encodeURIComponent(market)}&timeframe=${encodeURIComponent(timeframe)}`
  );

export const fetchDetails = (symbol: string, market: Market | string) =>
  request<DetailsResponse>(
    `/api/details?symbol=${encodeURIComponent(symbol)}&market=${encodeURIComponent(market)}`
  );

export const fetchQuote = (market: Market | string, ticker: string) =>
  request<Quote>(`/api/market_data/quote/${encodeURIComponent(market)}/${encodeURIComponent(ticker)}`);

export const fetchWatchlist = () => request<WatchlistResponse>(`/api/watchlist`);

export const addToWatchlist = (ticker: string, market: Market) =>
  request<{ status: string }>(`/api/watchlist`, {
    method: "POST",
    body: JSON.stringify({ ticker, market }),
  });

export const removeFromWatchlist = (ticker: string) =>
  request<{ status: string }>(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });

export const fetchPaperPortfolio = () => request<PaperPortfolioResponse>(`/api/paper/portfolio`);

export const fetchPaperTrades = () => request<PaperTradesResponse>(`/api/paper/trades`);

export const openPaperTrade = (trade: PaperTradeCreate) =>
  request<PaperTrade>(`/api/paper/trades`, {
    method: "POST",
    body: JSON.stringify(trade),
  });

export const closePaperTrade = (tradeId: string) =>
  request<{ status: string; trade: PaperTrade }>(`/api/paper/trades/${encodeURIComponent(tradeId)}`, {
    method: "DELETE",
  });
