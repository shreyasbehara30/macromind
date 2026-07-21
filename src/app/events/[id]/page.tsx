"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { fetchEventImpact } from "@/lib/api";

export default function EventDrillDown() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['event-impact', id],
    queryFn: () => fetchEventImpact(id),
    retry: 2,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="text-text-secondary animate-pulse">Running AI Impact Analysis...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-md mx-auto">
        <div className="w-16 h-16 rounded-full bg-danger/10 flex items-center justify-center mb-4">
          <span className="material-symbols-outlined text-danger text-3xl">error</span>
        </div>
        <h2 className="text-xl font-bold text-text-primary mb-2">Analysis Failed</h2>
        <p className="text-text-secondary mb-6 text-sm">{error instanceof Error ? error.message : 'Unknown error occurred'}</p>
        <div className="flex gap-4">
          <button onClick={() => router.back()} className="px-4 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high transition-colors text-sm">
            Go Back
          </button>
          <button onClick={() => refetch()} className="px-4 py-2 rounded-lg bg-primary text-on-primary hover:bg-primary/90 transition-colors text-sm shadow-[0_0_10px_rgba(14,165,201,0.3)]">
            Retry Analysis
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="w-full flex flex-col pb-10">
      <button onClick={() => router.back()} className="flex items-center gap-2 text-text-secondary hover:text-primary transition-colors mb-6 w-fit">
        <span className="material-symbols-outlined text-sm">arrow_back</span>
        <span className="text-sm font-medium">Back to Events</span>
      </button>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
        <div className="flex items-center gap-3 mb-3">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${data.severity === 'High' ? 'bg-danger/20 text-danger animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.4)]' : data.severity === 'Medium' ? 'bg-warning/20 text-warning' : 'bg-success/20 text-success'}`}>
            {data.severity} SEVERITY
          </span>
          <span className="text-sm text-text-secondary tracking-wide">AI CLASSIFIED</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-text-primary mb-4 leading-tight">{data.title}</h1>
        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-primary">
          <p className="text-text-secondary leading-relaxed">{data.ai_analysis}</p>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Chain Reaction Flow Diagram */}
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }} className="glass-card p-6 rounded-2xl">
          <h2 className="text-xl font-bold text-text-primary mb-6 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">account_tree</span>
            Impact Chain
          </h2>
          
          <div className="relative pl-8 space-y-8 before:absolute before:inset-y-0 before:left-[15px] before:w-0.5 before:bg-outline-variant">
            {data.chain_reaction?.map((node, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 + (i * 0.15) }}
                className="relative"
              >
                <div className="absolute -left-[35.5px] top-1.5 w-4 h-4 rounded-full bg-surface border-2 border-primary z-10 shadow-[0_0_8px_rgba(14,165,201,0.5)]"></div>
                <div className="bg-surface-container p-4 rounded-xl border border-outline-variant hover:border-primary/50 transition-colors">
                  <p className="text-text-primary text-sm leading-relaxed">{node}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Affected Stocks */}
        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }} className="glass-card p-6 rounded-2xl border-t-4 border-t-success relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-success/10 rounded-full blur-3xl pointer-events-none"></div>
            <h2 className="text-xl font-bold text-success mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined">trending_up</span>
              Beneficiaries
            </h2>
            <div className="space-y-3">
              {data.stocks?.beneficiaries?.map((stock, i) => (
                <motion.div 
                  initial={{ opacity: 0, rotateX: -90 }}
                  animate={{ opacity: 1, rotateX: 0 }}
                  transition={{ delay: 0.6 + (i * 0.1), type: "spring" }}
                  key={i} 
                  className="p-4 bg-surface-container rounded-xl border border-outline-variant flex items-start gap-4 hover:border-success/50 transition-colors"
                >
                  <div className="bg-success/10 text-success font-bold px-3 py-1.5 rounded-lg border border-success/20">
                    {stock.ticker}
                  </div>
                  <p className="text-sm text-text-secondary mt-1">{stock.reason}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }} className="glass-card p-6 rounded-2xl border-t-4 border-t-danger relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-danger/10 rounded-full blur-3xl pointer-events-none"></div>
            <h2 className="text-xl font-bold text-danger mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined">trending_down</span>
              At Risk
            </h2>
            <div className="space-y-3">
              {data.stocks?.pressure?.map((stock, i) => (
                <motion.div 
                  initial={{ opacity: 0, rotateX: -90 }}
                  animate={{ opacity: 1, rotateX: 0 }}
                  transition={{ delay: 0.8 + (i * 0.1), type: "spring" }}
                  key={i} 
                  className="p-4 bg-surface-container rounded-xl border border-outline-variant flex items-start gap-4 hover:border-danger/50 transition-colors"
                >
                  <div className="bg-danger/10 text-danger font-bold px-3 py-1.5 rounded-lg border border-danger/20">
                    {stock.ticker}
                  </div>
                  <p className="text-sm text-text-secondary mt-1">{stock.reason}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
