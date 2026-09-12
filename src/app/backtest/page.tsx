"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import toast from "react-hot-toast";
import {
  runBacktest,
  runMonteCarlo,
  fetchWatchlist,
  type BacktestResponse,
  type Market,
  type MonteCarloResponse,
} from "@/lib/api";

const MARKETS: Market[] = ["NSE", "US", "CRYPTO", "BSE", "COMMODITY", "FOREX"];

function useLineChart(
  ref: React.RefObject<HTMLDivElement | null>,
  series: { time: number; value: number }[][],
  colors: string[]
) {
  useEffect(() => {
    if (!ref.current || series.every((s) => s.length === 0)) return;
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "#131722" }, textColor: "#787B86" },
      grid: { vertLines: { color: "#2A2E39" }, horzLines: { color: "#2A2E39" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#2A2E39" },
      timeScale: { borderColor: "#2A2E39" },
      autoSize: true,
    });
    series.forEach((s, i) => {
      const line = chart.addLineSeries({ color: colors[i % colors.length], lineWidth: 2 });
      line.setData(s as unknown as Parameters<typeof line.setData>[0]);
    });
    return () => chart.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(series.map((s) => s.length))]);
}

export default function BacktestPage() {
  const [tab, setTab] = useState<"backtest" | "montecarlo">("backtest");
  const [ticker, setTicker] = useState("RELIANCE.NS");
  const [market, setMarket] = useState<Market>("NSE");
  const [strategy, setStrategy] = useState("ma_cross");
  const [fast, setFast] = useState(20);
  const [slow, setSlow] = useState(50);
  const [mcDays, setMcDays] = useState(30);
  // Declarative run requests: set on click, consumed by the queries below.
  // (An earlier enabled:false + refetch() pattern silently never fired.)
  const [btRequest, setBtRequest] = useState<null | { ticker: string; market: Market; strategy: string; fast: number; slow: number }>(null);
  const [mcRequest, setMcRequest] = useState<null | { ticker: string; market: Market; days: number }>(null);
  const equityRef = useRef<HTMLDivElement>(null);
  const mcRef = useRef<HTMLDivElement>(null);

  const { data: watchlistData } = useQuery({ queryKey: ["watchlist"], queryFn: fetchWatchlist });

  const {
    data: result,
    isFetching: btFetching,
    isError: btError,
    error: btErr,
  } = useQuery({
    queryKey: ["backtest", btRequest],
    queryFn: () => runBacktest(btRequest!.ticker, btRequest!.market, btRequest!.strategy, btRequest!.fast, btRequest!.slow),
    enabled: btRequest !== null,
    retry: 0,
  });

  const {
    data: mc,
    isFetching: mcFetching,
    isError: mcError,
    error: mcErr,
  } = useQuery({
    queryKey: ["montecarlo", mcRequest],
    queryFn: () => runMonteCarlo(mcRequest!.ticker, mcRequest!.market, mcRequest!.days, 200),
    enabled: mcRequest !== null,
    retry: 0,
  });

  useEffect(() => {
    if (btError) toast.error(btErr instanceof Error ? btErr.message : "Backtest failed");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [btError]);

  useLineChart(equityRef, result ? [result.equity_curve] : [], ["#0EA5C9"]);

  const mcSeries = mc
    ? [
        mc.p90_path.map((v, i) => ({ time: mc.last_time + (i + 1) * 86400, value: v })),
        mc.median_path.map((v, i) => ({ time: mc.last_time + (i + 1) * 86400, value: v })),
        mc.p10_path.map((v, i) => ({ time: mc.last_time + (i + 1) * 86400, value: v })),
      ]
    : [];
  useLineChart(mcRef, mcSeries, ["#26A69A", "#0EA5C9", "#EF5350"]);

  const m = result?.metrics;
  const cards: { label: string; value: string; good?: boolean }[] = m
    ? [
        { label: "Strategy return", value: `${m.total_return_pct}%`, good: m.total_return_pct >= 0 },
        { label: "Buy & hold", value: `${m.buy_hold_return_pct}%`, good: m.buy_hold_return_pct >= 0 },
        { label: "Trades", value: `${m.num_trades}` },
        { label: "Win rate", value: `${m.win_rate_pct}%` },
        { label: "Max drawdown", value: `${m.max_drawdown_pct}%`, good: false },
        { label: "Sharpe (ann.)", value: `${m.sharpe_daily_annualised}` },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4 p-4 h-full overflow-y-auto">
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Backtest Lab</h1>
          <p className="text-sm text-text-secondary mt-1">
            Strategies on real history, closed candles only. Past performance never implies future returns.
          </p>
        </div>
        <div className="flex gap-1 bg-bg-secondary border border-border-dark rounded-lg p-1">
          {(["backtest", "montecarlo"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                tab === t ? "bg-bg-tertiary text-text-primary" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {t === "backtest" ? "Strategy" : "Monte Carlo"}
            </button>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex flex-wrap items-end gap-3 flex-shrink-0">
        <div>
          <label className="block text-xs text-text-secondary mb-1">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="w-40 bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-text-secondary mb-1">Market</label>
          <select
            value={market}
            onChange={(e) => setMarket(e.target.value as Market)}
            className="bg-bg-primary border border-border-dark rounded p-2 text-text-primary text-sm"
          >
            {MARKETS.map((mk) => (
              <option key={mk} value={mk}>{mk}</option>
            ))}
          </select>
        </div>
        {tab === "backtest" ? (
          <>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Strategy</label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="bg-bg-primary border border-border-dark rounded p-2 text-text-primary text-sm"
              >
                <option value="ma_cross">MA Crossover</option>
                <option value="buy_hold">Buy &amp; Hold</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Fast MA</label>
              <input type="number" min={2} value={fast} onChange={(e) => setFast(Number(e.target.value))} className="w-20 bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm" />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Slow MA</label>
              <input type="number" min={3} value={slow} onChange={(e) => setSlow(Number(e.target.value))} className="w-20 bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm" />
            </div>
            <button
              onClick={() => setBtRequest({ ticker: ticker.trim(), market, strategy, fast, slow })}
              disabled={btFetching}
              className="bg-teal text-white px-6 py-2 rounded-lg text-sm font-bold hover:bg-teal/90 transition-colors disabled:opacity-50"
            >
              {btFetching ? "Running…" : "Run Backtest"}
            </button>
          </>
        ) : (
          <>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Days</label>
              <input type="number" min={5} max={90} value={mcDays} onChange={(e) => setMcDays(Number(e.target.value))} className="w-20 bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm" />
            </div>
            <button
              onClick={() => setMcRequest({ ticker: ticker.trim(), market, days: mcDays })}
              disabled={mcFetching}
              className="bg-teal text-white px-6 py-2 rounded-lg text-sm font-bold hover:bg-teal/90 transition-colors disabled:opacity-50"
            >
              {mcFetching ? "Simulating…" : "Run Simulation"}
            </button>
          </>
        )}
        {(watchlistData?.watchlist ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1.5 ml-1">
            {(watchlistData?.watchlist ?? []).slice(0, 8).map((r) => (
              <button
                key={`${r.market}:${r.ticker}`}
                onClick={() => { setTicker(r.ticker); setMarket(r.market); }}
                className="text-[11px] px-2 py-1 rounded border border-border-dark text-text-secondary hover:text-text-primary transition-colors"
              >
                {r.ticker}
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === "backtest" ? (
        result ? (
          <BacktestResult result={result} cards={cards} equityRef={equityRef} />
        ) : btError ? (
          <EmptyState text={`Backtest failed: ${btErr instanceof Error ? btErr.message : "unknown error"}`} error />
        ) : (
          <EmptyState text={btFetching ? "Crunching 5 years of closed candles…" : "Set a symbol and run a backtest."} />
        )
      ) : mc ? (
        <MonteCarloResult mc={mc} mcRef={mcRef} />
      ) : mcError ? (
        <EmptyState text={`Simulation failed: ${mcErr instanceof Error ? mcErr.message : "unknown error"}`} error />
      ) : (
        <EmptyState text={mcFetching ? "Simulating 200 paths…" : "Set a symbol and run a simulation. A fan chart of what could happen — not a prediction."} />
      )}
    </div>
  );
}

function EmptyState({ text, error }: { text: string; error?: boolean }) {
  return (
    <div className={`flex-1 bg-bg-secondary border rounded-xl flex items-center justify-center text-sm min-h-[300px] ${error ? "border-tv-red text-tv-red" : "border-border-dark text-text-secondary"}`}>
      {text}
    </div>
  );
}

function BacktestResult({
  result,
  cards,
  equityRef,
}: {
  result: BacktestResponse;
  cards: { label: string; value: string; good?: boolean }[];
  equityRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 flex-shrink-0">
        {cards.map((c) => (
          <div key={c.label} className="bg-bg-secondary border border-border-dark rounded-xl p-3">
            <div className="text-[11px] text-text-secondary uppercase tracking-wider mb-1">{c.label}</div>
            <div className={`text-lg font-bold mono ${c.good === undefined ? "text-text-primary" : c.good ? "text-tv-green" : "text-tv-red"}`}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
      <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex-shrink-0">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Growth of ₹1 / $1 · {result.ticker} · {result.bars_used} closed bars
        </h2>
        <div ref={equityRef} className="w-full h-[260px] relative" />
        <p className="text-[11px] text-text-secondary mt-2">{result.assumptions}</p>
      </div>
      <div className="bg-bg-secondary border border-border-dark rounded-xl overflow-hidden flex-shrink-0">
        <h2 className="text-sm font-semibold text-text-primary px-4 pt-3 pb-1">Trades (latest {result.trades.length})</h2>
        <table className="w-full text-sm text-left whitespace-nowrap">
          <thead className="text-xs text-text-secondary">
            <tr>
              <th className="px-4 py-2 font-medium">Side</th>
              <th className="px-4 py-2 font-medium text-right">Entry</th>
              <th className="px-4 py-2 font-medium text-right">Exit</th>
              <th className="px-4 py-2 font-medium text-right">P&amp;L %</th>
            </tr>
          </thead>
          <tbody>
            {result.trades.slice().reverse().map((t, i) => (
              <tr key={i} className="border-t border-border-dark/50">
                <td className="px-4 py-2 text-text-primary">{t.side}</td>
                <td className="px-4 py-2 text-right mono">{t.entry.toFixed(2)}</td>
                <td className="px-4 py-2 text-right mono">{t.exit.toFixed(2)}</td>
                <td className={`px-4 py-2 text-right mono font-bold ${t.pnl_pct >= 0 ? "text-tv-green" : "text-tv-red"}`}>
                  {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct}%
                </td>
              </tr>
            ))}
            {result.trades.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-text-secondary">No trades fired.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function MonteCarloResult({
  mc,
  mcRef,
}: {
  mc: MonteCarloResponse;
  mcRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-shrink-0">
        {[
          { label: `Median ${mc.days}d`, value: `${mc.projected_median_pct}%` },
          { label: "P10 (downside)", value: `${mc.projected_p10_pct}%` },
          { label: "P90 (upside)", value: `${mc.projected_p90_pct}%` },
          { label: "Daily vol", value: `${mc.daily_vol_pct}%` },
        ].map((c) => (
          <div key={c.label} className="bg-bg-secondary border border-border-dark rounded-xl p-3">
            <div className="text-[11px] text-text-secondary uppercase tracking-wider mb-1">{c.label}</div>
            <div className="text-lg font-bold mono text-text-primary">{c.value}</div>
          </div>
        ))}
      </div>
      <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex-shrink-0">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          {mc.paths} simulated paths · {mc.ticker} from {mc.last_close}
        </h2>
        <div ref={mcRef} className="w-full h-[260px] relative" />
        <p className="text-[11px] text-text-secondary mt-2">{mc.disclaimer}</p>
      </div>
    </>
  );
}
