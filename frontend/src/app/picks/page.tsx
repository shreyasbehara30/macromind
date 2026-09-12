"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@radix-ui/react-dialog";
import toast from "react-hot-toast";
import { fetchPicks, openPaperTrade, type Pick } from "@/lib/api";

export default function PicksPage() {
  const [selectedMarket, setSelectedMarket] = useState("NSE");
  const [selectedHorizon, setSelectedHorizon] = useState("Short Term");
  const [simulateTarget, setSimulateTarget] = useState<Pick | null>(null);
  const [tradeForm, setTradeForm] = useState({ qty: 1 });

  const { data: picksData, isFetching } = useQuery({
    queryKey: ['picks', selectedMarket, selectedHorizon],
    queryFn: () => fetchPicks(selectedMarket, selectedHorizon),
  });

  const handleSimulateTrade = async () => {
    if (!simulateTarget) return;
    try {
      // Conservative edge of the entry zone: LONG fills at the high, SHORT at the low.
      const entryPrice =
        simulateTarget.side === "LONG" ? simulateTarget.entry_high : simulateTarget.entry_low;

      await openPaperTrade({
        ticker: simulateTarget.ticker,
        market: simulateTarget.market,
        direction: simulateTarget.side,
        quantity: tradeForm.qty,
        entry_price: entryPrice,
        target_price: simulateTarget.target,
        stop_loss_price: simulateTarget.stop_loss,
      });
      toast.success("Trade Placed!");
      setSimulateTarget(null);
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-secondary border border-border-dark rounded-xl overflow-hidden p-4">
      
      {/* Header & Controls */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">AI Stock Picks</h1>
          <p className="text-sm text-text-secondary mt-1">High probability setups identified by MacroMind Agent.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex bg-bg-primary rounded p-1 border border-border-dark">
            {["NSE", "US", "CRYPTO"].map(m => (
              <button
                key={m}
                onClick={() => setSelectedMarket(m)}
                className={`px-3 py-1 text-sm rounded transition-colors ${selectedMarket === m ? 'bg-bg-tertiary text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="flex bg-bg-primary rounded p-1 border border-border-dark">
            {["Short Term", "Medium Term", "Long Term"].map(h => (
              <button
                key={h}
                onClick={() => setSelectedHorizon(h)}
                className={`px-3 py-1 text-sm rounded transition-colors ${selectedHorizon === h ? 'bg-bg-tertiary text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
              >
                {h}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Picks Table (loading never blocks clicks: stale rows stay interactive) */}
      <div className="flex-1 overflow-auto border border-border-dark rounded-lg bg-bg-primary relative">
        {isFetching && (
          <div className="absolute top-0 left-0 right-0 h-0.5 z-10 overflow-hidden pointer-events-none">
            <div className="h-full w-1/3 bg-teal animate-[loadingbar_1s_linear_infinite]" />
          </div>
        )}
        <style>{`@keyframes loadingbar { 0% { margin-left: -33%; } 100% { margin-left: 100%; } }`}</style>
        <table className="w-full text-sm text-left whitespace-nowrap">
          <thead className="text-xs text-text-secondary bg-bg-secondary sticky top-0 z-0">
            <tr>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Symbol</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Action</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Entry</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Target</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Stop Loss</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Confidence</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Trigger Event</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark"></th>
            </tr>
          </thead>
          <tbody>
            {picksData?.picks?.map((pick, i) => {
              const isLong = pick.side === "LONG";

              return (
                <tr key={i} className="border-b border-border-dark hover:bg-bg-tertiary transition-colors group">
                  <td className="px-4 py-3 font-bold text-text-primary">
                    <Link href={`/symbol/${pick.ticker}?market=${pick.market}`} className="hover:text-teal">{pick.ticker}</Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${isLong ? 'bg-tv-green/20 text-tv-green' : 'bg-tv-red/20 text-tv-red'}`}>
                      {pick.side}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right mono">
                    {pick.entry_low === pick.entry_high
                      ? pick.entry_low.toFixed(2)
                      : `${pick.entry_low.toFixed(2)} – ${pick.entry_high.toFixed(2)}`}
                  </td>
                  <td className="px-4 py-3 text-right mono text-tv-green">{pick.target.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right mono text-tv-red">{pick.stop_loss.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-teal"
                          style={{ width: `${pick.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-text-secondary">{Math.round(pick.confidence * 100)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col">
                      <span className="text-xs font-medium text-text-primary truncate max-w-[200px]" title={pick.reason ?? undefined}>{pick.reason ?? "—"}</span>
                      {pick.event && <span className="text-[10px] text-text-secondary">{pick.event}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Dialog>
                      <DialogTrigger asChild>
                        <button
                          className="opacity-0 group-hover:opacity-100 transition-opacity bg-teal hover:bg-teal/90 text-white text-xs px-3 py-1.5 rounded font-medium"
                          onClick={() => setSimulateTarget(pick)}
                        >
                          Simulate
                        </button>
                      </DialogTrigger>
                      <DialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm bg-bg-secondary border border-border-dark rounded-xl shadow-2xl p-6 z-[100]">
                        <DialogTitle className="text-lg font-bold mb-4">Simulate Trade</DialogTitle>
                        {simulateTarget && (
                          <div className="space-y-4">
                            <div className="flex justify-between items-center bg-bg-primary p-3 rounded border border-border-dark">
                              <span className="font-bold text-text-primary">{simulateTarget.ticker}</span>
                              <span className={`px-2 py-0.5 rounded text-xs font-bold ${simulateTarget.side === 'LONG' ? 'bg-tv-green/20 text-tv-green' : 'bg-tv-red/20 text-tv-red'}`}>
                                {simulateTarget.side}
                              </span>
                            </div>
                            <div>
                              <label className="block text-xs text-text-secondary mb-1">Quantity</label>
                              <input 
                                type="number" 
                                min="1"
                                className="w-full bg-bg-primary border border-border-dark rounded p-2 text-text-primary mono text-sm"
                                value={tradeForm.qty}
                                onChange={e => setTradeForm({ qty: Number(e.target.value) })}
                              />
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                              <div>
                                <span className="block text-[10px] text-text-secondary mb-1">
                                  Entry ({simulateTarget.side === "LONG" ? "zone high" : "zone low"})
                                </span>
                                <span className="mono text-sm">
                                  {(simulateTarget.side === "LONG" ? simulateTarget.entry_high : simulateTarget.entry_low).toFixed(2)}
                                </span>
                              </div>
                              <div>
                                <span className="block text-[10px] text-text-secondary mb-1">Target</span>
                                <span className="mono text-sm text-tv-green">{simulateTarget.target.toFixed(2)}</span>
                              </div>
                              <div>
                                <span className="block text-[10px] text-text-secondary mb-1">Stop</span>
                                <span className="mono text-sm text-tv-red">{simulateTarget.stop_loss.toFixed(2)}</span>
                              </div>
                            </div>
                            <button 
                              onClick={handleSimulateTrade}
                              className="w-full bg-teal hover:bg-teal/90 text-white py-2 rounded font-medium mt-4"
                            >
                              Place Order
                            </button>
                          </div>
                        )}
                      </DialogContent>
                    </Dialog>
                  </td>
                </tr>
              )
            })}

            {!isFetching && !picksData?.picks?.length && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-text-secondary">
                  No picks available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
