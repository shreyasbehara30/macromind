"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, use } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@radix-ui/react-dialog";
import toast from "react-hot-toast";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchDetails,
  fetchHistory,
  fetchQuote,
  fetchDepth,
  fetchProjection,
  addToWatchlist as apiAddToWatchlist,
  openPaperTrade,
  type Market,
} from "@/lib/api";

const KNOWN_MARKETS: Market[] = ["NSE", "BSE", "US", "CRYPTO", "COMMODITY", "FOREX"];

export default function SymbolDetail({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker: encodedTicker } = use(params);
  const ticker = decodeURIComponent(encodedTicker);
  const { user } = useAuth();
  const searchParams = useSearchParams();

  // Market is supplied explicitly by whoever linked here. It is never guessed
  // from the ticker string, and there is no default.
  const marketParam = searchParams.get("market");
  const market = KNOWN_MARKETS.includes(marketParam as Market) ? (marketParam as Market) : null;

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const projChartRef = useRef<HTMLDivElement>(null);
  const [timeframe, setTimeframe] = useState("1D");
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);
  const [tradeForm, setTradeForm] = useState({ side: "LONG", qty: 1, target: 0, stopLoss: 0 });

  // Live Price
  const { data: quote } = useQuery({
    queryKey: ['quote', market, ticker],
    queryFn: () => fetchQuote(market!, ticker),
    refetchInterval: 10000,
    enabled: market !== null,
  });

  // Fundamental Details
  const { data: details } = useQuery({
    queryKey: ['details', ticker, market],
    queryFn: () => fetchDetails(ticker, market!),
    enabled: market !== null,
  });

  // Chart data
  const { data: historyData } = useQuery({
    queryKey: ['history', ticker, market, timeframe],
    queryFn: () => fetchHistory(ticker, market!, timeframe),
    enabled: market !== null,
  });

  // Top-of-book + statistical projection (real quote feed math, labelled)
  const { data: depth } = useQuery({
    queryKey: ['depth', ticker, market],
    queryFn: () => fetchDepth(ticker, market!),
    enabled: market !== null,
    retry: 1,
    staleTime: 30000,
  });
  const { data: projection } = useQuery({
    queryKey: ['projection', ticker, market],
    queryFn: () => fetchProjection(ticker, market!, 30),
    enabled: market !== null,
    retry: 1,
    staleTime: 300000,
  });

  useEffect(() => {
    if (!projChartRef.current || !projection) return;
    const chart = createChart(projChartRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#131722" }, textColor: "#787B86" },
      grid: { vertLines: { color: "#2A2E39" }, horzLines: { color: "#2A2E39" } },
      rightPriceScale: { borderColor: "#2A2E39" },
      timeScale: { borderColor: "#2A2E39" },
      autoSize: true,
    });
    const mk = (color: string, width: 1 | 2) => {
      const s = chart.addLineSeries({ color, lineWidth: width });
      return s;
    };
    const upper = mk("#787B86", 1);
    const mid = mk("#0EA5C9", 2);
    const lower = mk("#787B86", 1);
    const rows = projection.times.map((t: number, i: number) => ({ time: t, upper: projection.upper[i], mid: projection.projection[i], lower: projection.lower[i] }));
    upper.setData(rows.map((r: any) => ({ time: r.time, value: r.upper })) as any);
    mid.setData(rows.map((r: any) => ({ time: r.time, value: r.mid })) as any);
    lower.setData(rows.map((r: any) => ({ time: r.time, value: r.lower })) as any);
    return () => chart.remove();
  }, [projection]);

  // Setup Chart
  useEffect(() => {
    if (!chartContainerRef.current || !historyData?.data || historyData.data.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#131722' },
        textColor: '#787B86',
      },
      grid: {
        vertLines: { color: '#2A2E39' },
        horzLines: { color: '#2A2E39' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#2A2E39',
      },
      timeScale: {
        borderColor: '#2A2E39',
        timeVisible: timeframe === "1m" || timeframe === "5m" || timeframe === "15m" || timeframe === "1H",
      },
      autoSize: true,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26A69A',
      downColor: '#EF5350',
      borderVisible: false,
      wickUpColor: '#26A69A',
      wickDownColor: '#EF5350',
    });

    candlestickSeries.setData(historyData.data as unknown as Parameters<typeof candlestickSeries.setData>[0]);

    // Add Volume Series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26A69A',
      priceFormat: { type: 'volume' },
      priceScaleId: '', 
    });

    chart.priceScale('').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const volumeData = historyData.data.map((d: any) => ({
      time: d.time,
      value: d.value,
      color: d.close >= d.open ? 'rgba(38, 166, 154, 0.4)' : 'rgba(239, 83, 80, 0.4)'
    }));
    
    volumeSeries.setData(volumeData);

    return () => {
      chart.remove();
    };
  }, [historyData, timeframe]);

  const handleSimulateTrade = async () => {
    if (!market || typeof quote?.price !== "number") {
      toast.error("No live quote for this symbol");
      return;
    }
    try {
      await openPaperTrade({
        ticker,
        market,
        direction: tradeForm.side as "LONG" | "SHORT",
        quantity: tradeForm.qty,
        entry_price: quote.price,
        target_price: tradeForm.target || null,
        stop_loss_price: tradeForm.stopLoss || null,
      });
      toast.success("Trade Placed!");
      setIsSimulateOpen(false);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const addToWatchlist = async () => {
    if (!market) {
      toast.error("Unknown market for this symbol");
      return;
    }
    try {
      await apiAddToWatchlist(ticker, market);
      toast.success("Added to Watchlist");
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const isPos = (quote?.change ?? 0) >= 0;
  const timeframes = ["1m", "5m", "15m", "1H", "1D", "1W"];

  if (!market) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center p-8">
        <span className="material-symbols-outlined text-4xl text-text-secondary opacity-50">help_center</span>
        <h1 className="text-2xl font-bold text-text-primary">{ticker}</h1>
        <p className="text-text-secondary max-w-md text-sm">
          No market specified for this symbol, and it is not in the symbol registry.
          Quotes, charts and fundamentals all require a market, and this app does not
          guess one from the ticker.
        </p>
        <Link href="/watchlist" className="text-teal text-sm hover:underline">Back to watchlist</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 h-full p-4">
      {/* Top Header Stats */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold">{ticker}</h1>
              <span className="px-2 py-0.5 bg-bg-tertiary border border-border-light text-text-secondary text-xs rounded">{market}</span>
            </div>
            <span className="text-text-secondary text-sm">{details?.longName || "Loading..."}</span>
          </div>
          
          <div className="flex items-baseline gap-3 ml-4 border-l border-border-dark pl-4">
            <span className="text-3xl mono font-semibold">{quote?.currency_symbol}{quote?.price?.toFixed(2) || "---"}</span>
            <span className={`text-lg mono ${isPos ? 'positive' : 'negative'}`}>
              {isPos ? '+' : ''}{quote?.change?.toFixed(2)} ({isPos ? '+' : ''}{quote?.change_percent?.toFixed(2)}%)
            </span>
          </div>
        </div>

        <div className="flex gap-6 text-sm">
          <div className="flex flex-col">
            <span className="text-text-secondary text-xs">Day Range</span>
            <span className="mono">{details?.dayLow?.toFixed(2) || "-"} - {details?.dayHigh?.toFixed(2) || "-"}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-text-secondary text-xs">Volume</span>
            <span className="mono">{details?.volume ? (details.volume / 1000000).toFixed(2) + "M" : "-"}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-text-secondary text-xs">52W Range</span>
            <span className="mono">{details?.fiftyTwoWeekLow?.toFixed(2) || "-"} - {details?.fiftyTwoWeekHigh?.toFixed(2) || "-"}</span>
          </div>
        </div>
      </div>

      {/* Main Split */}
      <div className="flex flex-col lg:flex-row gap-4 flex-1 overflow-hidden">
        
        {/* LEFT: Chart (70%) */}
        <div className="flex-[7] bg-bg-secondary border border-border-dark rounded-xl flex flex-col overflow-hidden h-full">
          <div className="h-12 border-b border-border-dark flex items-center px-2">
            {timeframes.map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`text-sm px-3 py-1.5 rounded transition-colors ${timeframe === tf ? 'text-teal font-medium' : 'text-text-secondary hover:text-text-primary'}`}
              >
                {tf}
              </button>
            ))}
          </div>
          <div ref={chartContainerRef} className="flex-1 w-full min-h-[300px] relative" />
        </div>

        {/* RIGHT: Actions & Info (30%) */}
        <div className="flex-[3] flex flex-col gap-4 overflow-y-auto min-w-[320px]">
          
          {/* Action Buttons */}
          <div className="grid grid-cols-2 gap-2">
            <button onClick={addToWatchlist} className="bg-bg-tertiary hover:bg-border-light border border-border-dark text-text-primary py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2">
              <span className="material-symbols-outlined text-[18px]">bookmark_add</span>
              Watchlist
            </button>
            
            <Dialog open={isSimulateOpen} onOpenChange={setIsSimulateOpen}>
              <DialogTrigger asChild>
                <button className="bg-teal hover:bg-teal/90 text-text-white py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2">
                  <span className="material-symbols-outlined text-[18px]">candlestick_chart</span>
                  Simulate
                </button>
              </DialogTrigger>
              <DialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-bg-secondary border border-border-dark rounded-xl shadow-2xl p-6 z-[100]">
                <DialogTitle className="text-xl font-bold mb-4 flex items-center gap-2">
                  Simulate Trade: {ticker}
                </DialogTitle>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-bg-primary border border-border-dark rounded-lg">
                    <span className="text-text-secondary">Current Price</span>
                    <span className="mono font-bold text-lg">{quote?.currency_symbol}{quote?.price?.toFixed(2)}</span>
                  </div>

                  <div className="flex gap-2">
                    <button 
                      onClick={() => setTradeForm({...tradeForm, side: "LONG"})}
                      className={`flex-1 py-2 rounded-lg font-medium border transition-colors ${tradeForm.side === "LONG" ? 'bg-tv-green/20 border-tv-green text-tv-green' : 'bg-bg-primary border-border-dark text-text-secondary'}`}
                    >
                      LONG (Buy)
                    </button>
                    <button 
                      onClick={() => setTradeForm({...tradeForm, side: "SHORT"})}
                      className={`flex-1 py-2 rounded-lg font-medium border transition-colors ${tradeForm.side === "SHORT" ? 'bg-tv-red/20 border-tv-red text-tv-red' : 'bg-bg-primary border-border-dark text-text-secondary'}`}
                    >
                      SHORT (Sell)
                    </button>
                  </div>

                  <div>
                    <label className="block text-sm text-text-secondary mb-1">Quantity</label>
                    <input type="number" min="1" value={tradeForm.qty} onChange={e => setTradeForm({...tradeForm, qty: Number(e.target.value)})} className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono" />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-text-secondary mb-1">Target Price</label>
                      <input type="number" value={tradeForm.target} onChange={e => setTradeForm({...tradeForm, target: Number(e.target.value)})} className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono" />
                    </div>
                    <div>
                      <label className="block text-sm text-text-secondary mb-1">Stop Loss</label>
                      <input type="number" value={tradeForm.stopLoss} onChange={e => setTradeForm({...tradeForm, stopLoss: Number(e.target.value)})} className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono" />
                    </div>
                  </div>

                  {/* Risk Reward Preview */}
                  <div className="bg-bg-primary p-3 rounded-lg border border-border-dark text-sm mt-4 space-y-1">
                    {typeof quote?.price === "number" && tradeForm.target > 0 && tradeForm.stopLoss > 0 ? (
                      <>
                        <div className="flex justify-between">
                          <span className="text-text-secondary">Est. Risk</span>
                          <span className="text-tv-red mono">${Math.abs((quote.price - tradeForm.stopLoss) * tradeForm.qty).toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-text-secondary">Est. Reward</span>
                          <span className="text-tv-green mono">${Math.abs((tradeForm.target - quote.price) * tradeForm.qty).toFixed(2)}</span>
                        </div>
                      </>
                    ) : (
                      <span className="text-text-secondary text-xs">Enter a target and stop loss to see risk/reward.</span>
                    )}
                  </div>

                  <button onClick={handleSimulateTrade} className="w-full bg-teal text-text-white py-3 rounded-lg font-bold hover:bg-teal/90 mt-2">
                    Open Position
                  </button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Top of Book (best bid/ask only — no full ladder in this feed) */}
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4">
            <h3 className="font-semibold text-text-primary mb-3">Top of Book</h3>
            {depth ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-tv-green mono font-bold">{depth.bid.toFixed(2)}</span>
                  <span className="text-text-secondary text-xs">BID × {depth.bid_size || "—"}</span>
                </div>
                <div className="flex h-1.5 rounded overflow-hidden bg-bg-primary">
                  <div
                    className="bg-tv-green"
                    style={{ width: `${depth.bid_size + depth.ask_size > 0 ? (depth.bid_size / (depth.bid_size + depth.ask_size)) * 100 : 50}%` }}
                  />
                  <div className="flex-1 bg-tv-red" />
                </div>
                <div className="flex justify-between">
                  <span className="text-tv-red mono font-bold">{depth.ask.toFixed(2)}</span>
                  <span className="text-text-secondary text-xs">ASK × {depth.ask_size || "—"}</span>
                </div>
                <div className="flex justify-between text-xs text-text-secondary pt-1">
                  <span>Spread {depth.spread.toFixed(2)} ({depth.spread_bps} bps)</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-text-secondary">No bid/ask in this feed for {ticker}.</p>
            )}
          </div>

          {/* 30-day statistical baseline (not a trained model) */}
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4">
            <h3 className="font-semibold text-text-primary mb-1">Projection · 30d</h3>
            <p className="text-[11px] text-text-secondary mb-2">Trend + volatility bands. Statistical baseline, not AI.</p>
            {projection ? (
              <div ref={projChartRef} className="w-full h-[160px] relative" />
            ) : (
              <p className="text-xs text-text-secondary">Not enough history for {ticker}.</p>
            )}
          </div>

          {/* Key Statistics */}
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex-1">
            <h3 className="font-semibold text-text-primary mb-4">Key Statistics</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-border-dark/50 pb-2">
                <span className="text-text-secondary">Market Cap</span>
                <span className="mono">{details?.marketCap ? (details.marketCap / 1e9).toFixed(2) + "B" : "-"}</span>
              </div>
              <div className="flex justify-between border-b border-border-dark/50 pb-2">
                <span className="text-text-secondary">P/E Ratio</span>
                <span className="mono">{details?.peRatio?.toFixed(2) || "-"}</span>
              </div>
              <div className="flex justify-between border-b border-border-dark/50 pb-2">
                <span className="text-text-secondary">Dividend Yield</span>
                <span className="mono">{details?.dividendYield ? details.dividendYield.toFixed(2) + "%" : "-"}</span>
              </div>
              <div className="flex justify-between pb-2">
                <span className="text-text-secondary">Sector</span>
                <span>{details?.sector || "-"}</span>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
