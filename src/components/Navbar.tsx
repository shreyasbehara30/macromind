"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@radix-ui/react-dialog";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchDashboard, searchSymbols } from "@/lib/api";

// Ticker item component
const TickerItem = ({ ticker, price, change, change_percent, currency_symbol }: any) => {
  const isPositive = change >= 0;
  return (
    <div className="flex items-center gap-2 px-4 border-r border-border-dark whitespace-nowrap shrink-0">
      <span className="text-sm font-medium text-text-primary">{ticker}</span>
      <span className="mono text-sm text-text-primary">{currency_symbol}{price?.toFixed(2)}</span>
      <span className={`mono text-sm ${isPositive ? 'positive' : 'negative'}`}>
        {isPositive ? '+' : ''}{change?.toFixed(2)} ({isPositive ? '+' : ''}{change_percent?.toFixed(2)}%)
      </span>
    </div>
  );
};

export default function Navbar() {
  const router = useRouter();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard_ticker'],
    queryFn: fetchDashboard,
    refetchInterval: 20000,
  });

  const { data: searchResults, isLoading: isSearching } = useQuery({
    queryKey: ['symbol_search', searchQuery],
    queryFn: () => searchSymbols(searchQuery),
    enabled: searchQuery.length > 0,
  });

  const tickers = dashboardData?.tickers || [];
  // Duplicate for seamless infinite scroll
  const scrollTickers = [...tickers, ...tickers, ...tickers, ...tickers];

  return (
    <div className="h-12 bg-bg-primary border-b border-border-dark flex items-center justify-between px-4 flex-shrink-0 z-50">
      
      {/* Ticker Strip */}
      <div className="flex-1 overflow-hidden relative mx-4 mask-edges h-full flex items-center">
        <div className="ticker-scroll h-full">
          {scrollTickers.map((t, i) => (
             <TickerItem key={i} {...t} />
          ))}
        </div>
        {/* Gradient masks for smooth fade out at edges */}
        <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-bg-primary to-transparent pointer-events-none" />
        <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-bg-primary to-transparent pointer-events-none" />
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-4">
        
        {/* Search Trigger */}
        <Dialog open={isSearchOpen} onOpenChange={setIsSearchOpen}>
          <DialogTrigger asChild>
            <button className="flex items-center gap-2 bg-bg-secondary hover:bg-bg-tertiary border border-border-dark rounded-md px-3 py-1.5 transition-colors text-text-secondary group">
              <span className="material-symbols-outlined text-[18px] group-hover:text-text-primary transition-colors">search</span>
              <span className="text-sm group-hover:text-text-primary transition-colors">Search symbols...</span>
              <div className="flex items-center gap-1 ml-4 text-xs font-mono bg-bg-primary border border-border-light rounded px-1.5 py-0.5">
                <span>Ctrl</span><span>K</span>
              </div>
            </button>
          </DialogTrigger>
          
          <AnimatePresence>
            {isSearchOpen && (
              <DialogContent asChild forceMount>
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95, y: -20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -20 }}
                  transition={{ duration: 0.15 }}
                  className="fixed top-[10vh] left-1/2 -translate-x-1/2 w-full max-w-lg bg-bg-secondary border border-border-dark rounded-xl shadow-2xl z-[100] overflow-hidden"
                >
                  <DialogTitle className="sr-only">Search Symbols</DialogTitle>
                  <div className="flex items-center gap-3 p-4 border-b border-border-dark">
                    <span className="material-symbols-outlined text-text-secondary">search</span>
                    <input 
                      type="text" 
                      placeholder="Search NSE, US, or Crypto symbols..."
                      className="flex-1 bg-transparent text-text-primary text-lg focus:outline-none placeholder-text-secondary"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      autoFocus
                    />
                    <button onClick={() => setIsSearchOpen(false)} className="text-xs bg-bg-tertiary border border-border-light rounded px-2 py-1 text-text-secondary hover:text-text-primary">
                      ESC
                    </button>
                  </div>
                  
                  <div className="max-h-[60vh] overflow-y-auto">
                    {searchQuery && searchResults?.symbols?.length === 0 && (
                      <div className="p-8 text-center text-text-secondary">
                        No symbols found for "{searchQuery}"
                      </div>
                    )}
                    
                    {searchResults?.symbols?.map((sym: any) => (
                      <button
                        key={sym.ticker}
                        className="w-full flex items-center justify-between p-4 hover:bg-bg-tertiary border-b border-border-dark/50 transition-colors text-left"
                        onClick={() => {
                          setIsSearchOpen(false);
                          router.push(`/symbol/${sym.ticker}`);
                        }}
                      >
                        <div>
                          <div className="text-text-primary font-medium">{sym.ticker}</div>
                          <div className="text-sm text-text-secondary">{sym.name}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs bg-bg-primary border border-border-dark rounded px-2 py-1 text-text-secondary">
                            {sym.market}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </motion.div>
              </DialogContent>
            )}
          </AnimatePresence>
        </Dialog>

        {/* Alerts */}
        <button className="relative material-symbols-outlined text-text-secondary hover:text-text-primary transition-colors text-[20px]">
          notifications
          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-tv-red rounded-full flex items-center justify-center text-[9px] font-bold text-text-white border-2 border-bg-primary">
            3
          </span>
        </button>

      </div>
    </div>
  );
}
