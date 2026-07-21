"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import toast from "react-hot-toast";
import Link from "next/link";
import { fetchPaperPortfolio, fetchPaperTrades, closePaperTrade } from "@/lib/api";
import { useQuotes, quoteKey } from "@/lib/useQuotes";

export default function PaperPortfolio() {
  const [activeTab, setActiveTab] = useState("positions");

  const { data: portfolio, refetch: refetchPortfolio } = useQuery({
    queryKey: ['paper_portfolio'],
    queryFn: fetchPaperPortfolio,
    refetchInterval: 10000
  });

  const { data: trades, refetch: refetchTrades } = useQuery({
    queryKey: ['paper_trades'],
    queryFn: fetchPaperTrades,
    refetchInterval: 10000
  });

  const closePosition = async (tradeId: string) => {
    try {
      await closePaperTrade(tradeId);
      toast.success("Position closed");
      refetchPortfolio();
      refetchTrades();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const cash = portfolio?.virtual_balance;
  const activePositions = trades?.open_trades ?? [];
  const historyTrades = trades?.closed_trades ?? [];

  // Live marks for open positions, fetched in parallel. A position whose quote
  // is unavailable has no mark and therefore no unrealized P&L: both render as
  // a dash. Entry price is never used as a stand-in, because that produces a
  // 0.00 P&L indistinguishable from a genuinely flat position.
  const { quotes } = useQuotes(activePositions.map((p) => ({ ticker: p.ticker, market: p.market })));

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary">Paper Portfolio</h1>
        <div className="flex gap-2">
          <button className="bg-bg-tertiary border border-border-dark px-4 py-2 rounded text-sm hover:text-text-primary transition-colors text-text-secondary">
            Settings
          </button>
          <button className="bg-teal text-white px-4 py-2 rounded text-sm font-medium hover:bg-teal/90 transition-colors shadow-lg shadow-teal/20">
            Reset Account
          </button>
        </div>
      </div>

      {/* Top Stats & Chart */}
      <div className="flex flex-col lg:flex-row gap-4 h-[240px] flex-shrink-0">
        
        {/* Key Metrics */}
        <div className="w-full lg:w-[320px] grid grid-cols-2 gap-4 h-full">
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex flex-col justify-center">
            <span className="text-xs text-text-secondary font-semibold uppercase tracking-wider mb-2">Virtual Balance</span>
            <span className="text-2xl font-bold mono tracking-tight">
              {typeof cash === "number" ? `$${cash.toFixed(2)}` : <span className="text-text-secondary font-normal text-base">No data</span>}
            </span>
          </div>
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex flex-col justify-center">
            <span className="text-xs text-text-secondary font-semibold uppercase tracking-wider mb-2">Win Rate</span>
            <span className="text-2xl font-bold mono tracking-tight text-text-primary/90">
              {typeof portfolio?.win_rate === "number" ? `${portfolio.win_rate.toFixed(1)}%` : <span className="text-text-secondary font-normal text-base">No data</span>}
            </span>
          </div>
          <div className="bg-bg-secondary border border-border-dark rounded-xl p-4 flex flex-col justify-center col-span-2">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-text-secondary font-semibold uppercase tracking-wider">Realized P&amp;L</span>
              <span className="text-xs text-text-secondary font-bold bg-bg-tertiary px-2 py-0.5 rounded">Closed trades only</span>
            </div>
            <div className="flex items-baseline gap-3">
              {typeof portfolio?.total_realized_pnl === "number" ? (
                <span className={`text-2xl font-bold mono tracking-tight ${portfolio.total_realized_pnl >= 0 ? 'text-tv-green' : 'text-tv-red'}`}>
                  {portfolio.total_realized_pnl >= 0 ? '+' : ''}{portfolio.total_realized_pnl.toFixed(2)}
                </span>
              ) : (
                <span className="text-base text-text-secondary">No data</span>
              )}
            </div>
          </div>
        </div>

        {/* Equity Curve Chart */}
        <div className="flex-1 bg-bg-secondary border border-border-dark rounded-xl p-4 h-full relative overflow-hidden">
          <div className="absolute top-4 left-4 z-10">
             <h2 className="text-sm font-semibold text-text-primary">Performance History</h2>
          </div>
          <div className="w-full h-full mt-6 flex flex-col items-center justify-center gap-2 text-center">
            <span className="material-symbols-outlined text-3xl text-text-secondary opacity-40">show_chart</span>
            <p className="text-sm text-text-secondary">No trade history yet.</p>
            <p className="text-xs text-text-secondary/70 max-w-[320px]">
              An equity curve requires closed trades with recorded exit prices. None are stored.
            </p>
          </div>
        </div>
      </div>

      {/* Tables Section */}
      <div className="flex-1 bg-bg-secondary border border-border-dark rounded-xl overflow-hidden flex flex-col min-h-[300px]">
        {/* Tabs */}
        <div className="h-12 border-b border-border-dark flex items-center px-2 flex-shrink-0">
          <button 
            onClick={() => setActiveTab("positions")}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'positions' ? 'border-teal text-text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}
          >
            Active Positions ({activePositions.length})
          </button>
          <button 
            onClick={() => setActiveTab("history")}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'history' ? 'border-teal text-text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}
          >
            Trade History ({historyTrades.length})
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-auto bg-bg-primary">
          <table className="w-full text-sm text-left whitespace-nowrap">
            <thead className="text-xs text-text-secondary bg-bg-secondary sticky top-0 z-10 shadow-[0_1px_0_#2A2E39]">
              <tr>
                <th className="px-4 py-3 font-medium">Symbol</th>
                <th className="px-4 py-3 font-medium">Side</th>
                <th className="px-4 py-3 font-medium text-right">Qty</th>
                <th className="px-4 py-3 font-medium text-right">Entry Price</th>
                {activeTab === 'positions' && <th className="px-4 py-3 font-medium text-right">Current Price</th>}
                <th className="px-4 py-3 font-medium text-right">Target</th>
                <th className="px-4 py-3 font-medium text-right">Stop Loss</th>
                {activeTab === 'positions' && <th className="px-4 py-3 font-medium text-right">Unrealized PnL</th>}
                {activeTab === 'history' && <th className="px-4 py-3 font-medium text-right">Realized PnL</th>}
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {activeTab === 'positions' ? (
                activePositions.map((p) => {
                  const isLong = p.direction === 'LONG';
                  const mark = quotes.get(quoteKey(p.market, p.ticker));

                  // No mark means no P&L. Not zero, not entry price: unknown.
                  const unrealised = mark
                    ? (isLong
                        ? (mark.price - p.entry_price) * p.quantity
                        : (p.entry_price - mark.price) * p.quantity)
                    : null;

                  return (
                    <tr key={p.id} className="border-b border-border-dark hover:bg-bg-tertiary transition-colors group">
                      <td className="px-4 py-3 font-bold text-text-primary">{p.ticker}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isLong ? 'bg-tv-green/20 text-tv-green' : 'bg-tv-red/20 text-tv-red'}`}>
                          {p.direction}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right mono">{p.quantity}</td>
                      <td className="px-4 py-3 text-right mono">{p.entry_price.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right mono font-medium text-text-primary">
                        {mark ? mark.price.toFixed(2) : <span className="text-text-secondary">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right mono text-tv-green">{p.target_price?.toFixed(2) ?? "-"}</td>
                      <td className="px-4 py-3 text-right mono text-tv-red">{p.stop_loss_price?.toFixed(2) ?? "-"}</td>
                      <td className={`px-4 py-3 text-right mono font-bold ${unrealised === null ? 'text-text-secondary' : unrealised >= 0 ? 'text-tv-green' : 'text-tv-red'}`}>
                        {unrealised === null
                          ? "—"
                          : `${unrealised >= 0 ? '+' : ''}${unrealised.toFixed(2)}`}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => closePosition(p.id)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity bg-bg-secondary hover:bg-tv-red border border-border-dark hover:border-tv-red text-text-primary hover:text-white px-3 py-1 rounded text-xs font-medium"
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  )
                })
              ) : (
                historyTrades.map((p) => {
                  const pnl = p.realized_pnl;
                  const isPos = (pnl ?? 0) >= 0;
                  return (
                    <tr key={p.id} className="border-b border-border-dark hover:bg-bg-tertiary transition-colors">
                      <td className="px-4 py-3 font-bold text-text-primary">{p.ticker}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${p.direction === 'LONG' ? 'bg-tv-green/20 text-tv-green' : 'bg-tv-red/20 text-tv-red'}`}>
                          {p.direction}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right mono">{p.quantity}</td>
                      <td className="px-4 py-3 text-right mono">{p.entry_price.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right mono text-tv-green">{p.target_price?.toFixed(2) ?? "-"}</td>
                      <td className="px-4 py-3 text-right mono text-tv-red">{p.stop_loss_price?.toFixed(2) ?? "-"}</td>
                      <td className={`px-4 py-3 text-right mono font-bold ${typeof pnl === "number" ? (isPos ? 'text-tv-green' : 'text-tv-red') : 'text-text-secondary'}`}>
                        {typeof pnl === "number" ? `${isPos ? '+' : ''}${pnl.toFixed(2)}` : "-"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-xs text-text-secondary bg-bg-secondary px-2 py-1 rounded border border-border-dark">{p.status.replace("closed_", "").toUpperCase()}</span>
                      </td>
                    </tr>
                  )
                })
              )}

              {activeTab === 'positions' && activePositions.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-text-secondary">
                    No active positions. Go to <Link href="/picks" className="text-teal hover:underline">Picks</Link> to simulate a trade.
                  </td>
                </tr>
              )}

              {activeTab === 'history' && historyTrades.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-text-secondary">
                    No trade history yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
