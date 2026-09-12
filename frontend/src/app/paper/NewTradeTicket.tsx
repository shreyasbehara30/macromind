"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import toast from "react-hot-toast";
import {
  fetchHistory,
  fetchQuote,
  fetchWatchlist,
  openPaperTrade,
  type Market,
} from "@/lib/api";

const MARKETS: Market[] = ["NSE", "US", "CRYPTO", "BSE", "COMMODITY", "FOREX"];

/**
 * Trade ticket with a live mini-chart, for opening paper positions without
 * leaving the portfolio page. Entry is always the live quote at submit time —
 * never a typed-in price — so a position can never open at a level the
 * asset never traded at.
 */
export default function NewTradeTicket({ onPlaced }: { onPlaced: () => void }) {
  // Input commits explicitly (Load / Enter / chip): every keystroke must not
  // fire quote+history fetches, which 502-spams the console for half-typed
  // tickers like "N" on the way to a real symbol.
  const [input, setInput] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");
  const [market, setMarket] = useState<Market>("US");
  const [side, setSide] = useState<"LONG" | "SHORT">("LONG");
  const [qty, setQty] = useState(10);
  const [target, setTarget] = useState(0);
  const [stopLoss, setStopLoss] = useState(0);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const { data: watchlistData } = useQuery({
    queryKey: ["watchlist"],
    queryFn: fetchWatchlist,
  });

  const {
    data: quote,
    isError: quoteError,
    error: quoteErr,
  } = useQuery({
    queryKey: ["quote", market, ticker],
    queryFn: () => fetchQuote(market, ticker),
    refetchInterval: 10000,
    enabled: ticker.trim().length > 0,
    retry: 1,
  });

  const { data: historyData } = useQuery({
    queryKey: ["history", ticker, market, "ticket-1D"],
    queryFn: () => fetchHistory(ticker, market, "1D"),
    enabled: ticker.trim().length > 0,
    retry: 1,
  });

  useEffect(() => {
    if (!chartContainerRef.current || !historyData?.data || historyData.data.length === 0) return;
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#131722" }, textColor: "#787B86" },
      grid: { vertLines: { color: "#2A2E39" }, horzLines: { color: "#2A2E39" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#2A2E39" },
      timeScale: { borderColor: "#2A2E39" },
      autoSize: true,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#26A69A",
      downColor: "#EF5350",
      borderVisible: false,
      wickUpColor: "#26A69A",
      wickDownColor: "#EF5350",
    });
    series.setData(historyData.data as unknown as Parameters<typeof series.setData>[0]);
    return () => chart.remove();
  }, [historyData]);

  const pick = (t: string, m: Market) => {
    setInput(t);
    setTicker(t);
    setMarket(m);
  };

  const commit = () => {
    const clean = input.trim().toUpperCase();
    if (clean) setTicker(clean);
  };

  const place = async () => {
    if (typeof quote?.price !== "number" || quote.price <= 0) {
      toast.error("No live quote — cannot open a position without a real mark");
      return;
    }
    if (!(qty > 0)) {
      toast.error("Quantity must be positive");
      return;
    }
    try {
      await openPaperTrade({
        ticker: ticker.trim(),
        market,
        direction: side,
        quantity: qty,
        entry_price: quote.price,
        target_price: target > 0 ? target : null,
        stop_loss_price: stopLoss > 0 ? stopLoss : null,
        source: "ticket",
      });
      toast.success(`${side} ${qty} × ${ticker.trim()} @ ${quote.price.toFixed(2)}`);
      onPlaced();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const rows = watchlistData?.watchlist ?? [];

  return (
    <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex flex-col lg:flex-row gap-4">
      {/* Mini chart */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-text-primary">
            {ticker || "—"} <span className="text-text-secondary font-normal">· {market} · 1D</span>
          </span>
          <span className="mono text-sm font-bold text-text-primary">
            {typeof quote?.price === "number"
              ? `${quote.currency_symbol}${quote.price.toFixed(2)}`
              : <span className="text-text-secondary font-normal">—</span>}
          </span>
        </div>
        <div ref={chartContainerRef} className="w-full h-[220px] relative" />
        {rows.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {rows.map((r) => (
              <button
                key={`${r.market}:${r.ticker}`}
                onClick={() => pick(r.ticker, r.market)}
                className={`text-[11px] px-2 py-1 rounded border transition-colors ${
                  ticker === r.ticker && market === r.market
                    ? "border-teal text-teal"
                    : "border-border-dark text-text-secondary hover:text-text-primary"
                }`}
              >
                {r.ticker}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Form */}
      <div className="w-full lg:w-[300px] flex-shrink-0 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2">
            <label className="block text-xs text-text-secondary mb-1">Ticker</label>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value.toUpperCase())}
                onKeyDown={(e) => { if (e.key === "Enter") commit(); }}
                className="flex-1 min-w-0 bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
              />
              <button
                onClick={commit}
                className="bg-bg-tertiary border border-border-dark rounded px-4 text-sm text-text-primary hover:border-teal transition-colors"
              >
                Load
              </button>
            </div>
            {input.trim().toUpperCase() !== ticker && (
              <p className="text-[11px] text-amber mt-1">Press Load to fetch {input.trim().toUpperCase() || "—"}.</p>
            )}
            {quoteError && (
              <p className="text-[11px] text-tv-red mt-1">
                No live quote for {ticker} ({market}): {quoteErr instanceof Error ? quoteErr.message : "unknown symbol"}. Try RELIANCE.NS, AAPL, BTC.
              </p>
            )}
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-text-secondary mb-1">Market</label>
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value as Market)}
              className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary text-sm"
            >
              {MARKETS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-2">
          {(["LONG", "SHORT"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSide(s)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                side === s
                  ? s === "LONG"
                    ? "bg-tv-green/20 border-tv-green text-tv-green"
                    : "bg-tv-red/20 border-tv-red text-tv-red"
                  : "bg-bg-primary border-border-dark text-text-secondary"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div>
          <label className="block text-xs text-text-secondary mb-1">Quantity</label>
          <input
            type="number" min="0" value={qty}
            onChange={(e) => setQty(Number(e.target.value))}
            className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-text-secondary mb-1">Target</label>
            <input
              type="number" min="0" value={target}
              onChange={(e) => setTarget(Number(e.target.value))}
              className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-text-secondary mb-1">Stop loss</label>
            <input
              type="number" min="0" value={stopLoss}
              onChange={(e) => setStopLoss(Number(e.target.value))}
              className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
            />
          </div>
        </div>

        <button
          onClick={place}
          className="w-full bg-teal text-white py-2.5 rounded-lg text-sm font-bold hover:bg-teal/90 transition-colors"
        >
          Open {side} Position
        </button>
        <p className="text-[11px] text-text-secondary leading-snug">
          Entry is the live market price at submit time. Settlement auto-closes at target/stop.
        </p>
      </div>
    </div>
  );
}
