"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import { motion } from "framer-motion";
import Link from "next/link";
import { fetchDashboard, fetchGlobal, fetchHistory, type Market } from "@/lib/api";

// Each chart symbol carries its market explicitly. Market is never derived from
// the shape of the ticker string.
const CHART_SYMBOLS: { label: string; value: string; market: Market }[] = [
  { label: "Nifty 50", value: "^NSEI", market: "NSE" },
  { label: "S&P 500", value: "^GSPC", market: "US" },
  { label: "Bitcoin", value: "BTC", market: "CRYPTO" },
  { label: "Gold", value: "Gold", market: "COMMODITY" },
];

export default function Dashboard() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartSymbol, setChartSymbol] = useState(CHART_SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState("1D");
  
  // Dashboard overall data
  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 20000,
  });

  // Global markets board: one live quote per region/asset
  const { data: globalData } = useQuery({
    queryKey: ['global'],
    queryFn: fetchGlobal,
    refetchInterval: 30000,
  });

  // Chart data
  const { data: historyData } = useQuery({
    queryKey: ['history', chartSymbol.value, chartSymbol.market, timeframe],
    queryFn: () => fetchHistory(chartSymbol.value, chartSymbol.market, timeframe),
  });

  // Setup Chart
  useEffect(() => {
    if (!chartContainerRef.current || !historyData?.data) return;

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
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // set as an overlay
    });

    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 0.8, // highest point of the series will be at 80% of the chart height
        bottom: 0,
      },
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

  const timeframes = ["1m", "5m", "15m", "1H", "1D", "1W"];

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full">
      
      {/* LEFT PANE (65%) */}
      <div className="flex-1 flex flex-col gap-4 overflow-hidden h-full">
        {/* Main Chart Card */}
        <div className="bg-bg-secondary border border-border-dark rounded-xl flex flex-col min-h-[450px] flex-shrink-0">
          <div className="h-12 border-b border-border-dark flex items-center justify-between px-4">
            <div className="flex items-center gap-2">
              {CHART_SYMBOLS.map(s => (
                <button
                  key={s.value}
                  onClick={() => setChartSymbol(s)}
                  className={`text-sm px-3 py-1.5 rounded transition-colors ${chartSymbol.value === s.value ? 'bg-bg-tertiary text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 border-l border-border-dark pl-2">
              {timeframes.map(tf => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`text-sm px-2 py-1 rounded transition-colors ${timeframe === tf ? 'text-teal font-medium' : 'text-text-secondary hover:text-text-primary'}`}
                >
                  {tf}
                </button>
              ))}
              <Link
                href={`/symbol/${encodeURIComponent(chartSymbol.value)}?market=${chartSymbol.market}`}
                className="ml-2 text-sm px-3 py-1.5 rounded bg-teal/15 border border-teal/40 text-teal font-medium hover:bg-teal/25 transition-colors whitespace-nowrap"
              >
                Trade {chartSymbol.label}
              </Link>
            </div>
          </div>
          <div ref={chartContainerRef} className="flex-1 w-full min-h-[300px] relative" />
        </div>

        {/* Macro Events Feed */}
        <div className="bg-bg-secondary border border-border-dark rounded-xl flex-1 flex flex-col overflow-hidden">
          <div className="h-12 border-b border-border-dark flex items-center px-4">
            <h2 className="font-semibold text-text-primary">Live Macro Events</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-text-secondary border-b border-border-dark sticky top-0 bg-bg-secondary">
                <tr>
                  <th className="px-4 py-2 font-medium">Event</th>
                  <th className="px-4 py-2 font-medium">Impact</th>
                </tr>
              </thead>
              <tbody>
                {dashboardData?.top_events?.map((ev, i) => (
                  <tr key={i} className="border-b border-border-dark hover:bg-bg-tertiary cursor-pointer transition-colors">
                    <td className="px-4 py-3 text-text-primary">{ev.title}</td>
                    <td className="px-4 py-3">
                      {ev.severity ? (
                        <span className={`px-2 py-1 rounded text-xs ${ev.severity === 'High' ? 'bg-tv-red/10 text-tv-red' : 'bg-amber/10 text-amber'}`}>
                          {ev.severity}
                        </span>
                      ) : (
                        <span className="text-text-secondary text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))}

                {!dashboardData?.top_events?.length && (
                  <tr>
                    <td colSpan={2} className="px-4 py-8 text-center text-text-secondary">
                      No events available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RIGHT PANE (35%) */}
      <div className="w-full lg:w-[380px] bg-bg-secondary border border-border-dark rounded-xl flex flex-col overflow-y-auto h-full flex-shrink-0">
        <div className="h-12 border-b border-border-dark flex items-center px-4 sticky top-0 bg-bg-secondary z-10">
          <h2 className="font-semibold text-text-primary">Market Overview</h2>
        </div>
        
        <div className="p-4 space-y-6">
          {/* INDICES */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary mb-2">INDICES</h3>
            <div className="space-y-1">
              {!dashboardData?.tickers?.filter((t) => t.market === 'NSE' || t.market === 'US').length && (
                <p className="text-xs text-text-secondary py-1.5">No quotes available.</p>
              )}
              {dashboardData?.tickers?.filter((t) => t.market === 'NSE' || t.market === 'US').map((t) => {
                const isPos = t.change >= 0;
                return (
                  <div key={t.symbol} className="flex items-center justify-between py-1.5 hover:bg-bg-tertiary px-2 -mx-2 rounded transition-colors">
                    <span className="text-sm font-medium">{t.symbol}</span>
                    <div className="flex items-center gap-4 text-sm mono">
                      <span>{t.price?.toFixed(2)}</span>
                      <span className={`w-16 text-right ${isPos ? 'positive' : 'negative'}`}>{isPos ? '+' : ''}{t.change_percent?.toFixed(2)}%</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* CRYPTO */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary mb-2">CRYPTO</h3>
            <div className="space-y-1">
              {!dashboardData?.tickers?.filter((t) => t.market === 'CRYPTO').length && (
                <p className="text-xs text-text-secondary py-1.5">No quotes available.</p>
              )}
              {dashboardData?.tickers?.filter((t) => t.market === 'CRYPTO').map((t) => {
                const isPos = t.change >= 0;
                return (
                  <div key={t.symbol} className="flex items-center justify-between py-1.5 hover:bg-bg-tertiary px-2 -mx-2 rounded transition-colors">
                    <span className="text-sm font-medium">{t.symbol}</span>
                    <div className="flex items-center gap-4 text-sm mono">
                      <span>{t.price?.toFixed(2)}</span>
                      <span className={`w-16 text-right ${isPos ? 'positive' : 'negative'}`}>{isPos ? '+' : ''}{t.change_percent?.toFixed(2)}%</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
          
          {/* GLOBAL */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary mb-2">GLOBAL</h3>
            <div className="space-y-1">
              {!globalData?.markets?.length && (
                <p className="text-xs text-text-secondary py-1.5">No quotes available.</p>
              )}
              {(globalData?.markets ?? []).map((t) => {
                const isPos = t.change >= 0;
                return (
                  <div key={`${t.market}:${t.symbol}`} className="flex items-center justify-between py-1.5 hover:bg-bg-tertiary px-2 -mx-2 rounded transition-colors">
                    <span className="text-sm font-medium">{t.symbol} <span className="text-[10px] text-text-secondary">{t.market}</span></span>
                    <div className="flex items-center gap-4 text-sm mono">
                      <span>{t.price?.toFixed(2)}</span>
                      <span className={`w-16 text-right ${isPos ? 'positive' : 'negative'}`}>{isPos ? '+' : ''}{t.change_percent?.toFixed(2)}%</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* SECTOR MOMENTUM */}
          <div>
            <h3 className="text-xs font-semibold text-text-secondary mb-2">SECTOR MOMENTUM</h3>
            <div className="space-y-1">
              {dashboardData?.sector_momentum?.map((sec) => {
                const isPos = sec.change >= 0;
                const fillCount = Math.min(10, Math.max(1, Math.floor(Math.abs(sec.change) * 5)));
                const bar = "█".repeat(fillCount) + "░".repeat(10 - fillCount);
                return (
                  <div key={sec.sector} className="flex items-center justify-between py-1.5">
                    <span className="text-sm font-medium w-20">{sec.sector}</span>
                    <div className="flex items-center gap-3">
                      <span className={`mono text-xs ${isPos ? 'positive' : 'negative'}`}>{bar}</span>
                      <span className={`mono text-sm w-12 text-right ${isPos ? 'positive' : 'negative'}`}>{isPos ? '+' : ''}{sec.change}%</span>
                    </div>
                  </div>
                )
              })}
              {!dashboardData?.sector_momentum?.length && (
                <p className="text-xs text-text-secondary py-1.5">No sector data available.</p>
              )}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
