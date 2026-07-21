"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, Fragment } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { fetchWatchlist, removeFromWatchlist as apiRemoveFromWatchlist } from "@/lib/api";
import { useQuotes, quoteKey } from "@/lib/useQuotes";

export default function WatchlistPage() {
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  const { data: watchlistData, refetch, isError, error } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    refetchInterval: 10000,
  });

  const rows = watchlistData?.watchlist ?? [];

  // The watchlist API returns symbols only. Prices are hydrated client-side,
  // one parallel request per row against the same quote endpoint the rest of
  // the app uses. A row whose quote fails shows a neutral dash: no price, no
  // direction, and no red down-signal implying a fall that was never measured.
  const { quotes } = useQuotes(rows.map((r) => ({ ticker: r.ticker, market: r.market })));

  const removeFromWatchlist = async (ticker: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiRemoveFromWatchlist(ticker);
      toast.success("Removed from Watchlist");
      refetch();
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-secondary border border-border-dark rounded-xl overflow-hidden p-4">
      
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Watchlist</h1>
          <p className="text-sm text-text-secondary mt-1">Saved symbols with live quotes.</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto border border-border-dark rounded-lg bg-bg-primary">
        <table className="w-full text-sm text-left whitespace-nowrap relative">
          <thead className="text-xs text-text-secondary bg-bg-secondary sticky top-0 z-10">
            <tr>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Symbol</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark">Market</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Price</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Change</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark text-right">Change %</th>
              <th className="px-4 py-3 font-medium border-b border-border-dark"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => {
              const isExpanded = expandedSymbol === item.ticker;
              const quote = quotes.get(quoteKey(item.market, item.ticker));
              // Direction is only known when a change value exists. Absent data
              // is never coloured, so a missing quote cannot read as a decline.
              const dir =
                quote && typeof quote.change === "number"
                  ? quote.change >= 0
                    ? "positive"
                    : "negative"
                  : "";

              return (
                <Fragment key={item.ticker}>
                  <tr 
                    onClick={() => setExpandedSymbol(isExpanded ? null : item.ticker)}
                    className="border-b border-border-dark hover:bg-bg-tertiary cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3 font-bold text-text-primary">
                      <div className="flex flex-col">
                        <Link href={`/symbol/${item.ticker}?market=${item.market}`} className="hover:text-teal inline-block" onClick={(e) => e.stopPropagation()}>
                          {item.ticker}
                        </Link>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{item.market}</td>
                    <td className="px-4 py-3 text-right mono">
                      {quote ? `${quote.currency_symbol}${quote.price.toFixed(2)}` : <span className="text-text-secondary">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right mono ${dir}`}>
                      {quote && typeof quote.change === "number"
                        ? `${quote.change >= 0 ? "+" : ""}${quote.change.toFixed(2)}`
                        : <span className="text-text-secondary">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right mono ${dir}`}>
                      {quote && typeof quote.change_percent === "number"
                        ? `${quote.change_percent >= 0 ? "+" : ""}${quote.change_percent.toFixed(2)}%`
                        : <span className="text-text-secondary">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => removeFromWatchlist(item.ticker, e)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-text-secondary hover:text-tv-red material-symbols-outlined text-[20px]"
                        title="Remove"
                      >
                        close
                      </button>
                    </td>
                  </tr>
                  
                  {/* Expanded Row Content */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.tr
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                      >
                        <td colSpan={6} className="px-4 py-3 bg-bg-secondary border-b border-border-dark overflow-hidden">
                          <div className="flex justify-end items-center bg-bg-primary rounded border border-border-dark p-3">
                            <div className="flex gap-2">
                              <Link 
                                href={`/symbol/${item.ticker}?market=${item.market}`}
                                className="bg-bg-tertiary hover:bg-border-light border border-border-dark text-text-primary px-4 py-1.5 rounded text-xs font-medium transition-colors"
                              >
                                Full Chart
                              </Link>
                              <Link
                                href={`/symbol/${item.ticker}?market=${item.market}`}
                                className="bg-teal hover:bg-teal/90 text-white px-4 py-1.5 rounded text-xs font-medium transition-colors"
                              >
                                Simulate Trade
                              </Link>
                            </div>
                          </div>
                        </td>
                      </motion.tr>
                    )}
                  </AnimatePresence>
                </Fragment>
              )
            })}
            
            {isError && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-tv-red">
                  Watchlist unavailable: {error instanceof Error ? error.message : "storage error"}
                </td>
              </tr>
            )}

            {!isError && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-text-secondary">
                  Your watchlist is empty. Use the search bar (Ctrl+K) to add symbols.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
