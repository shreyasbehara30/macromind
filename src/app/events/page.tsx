"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchEvents, fetchEventImpact } from "@/lib/api";

export default function EventsPage() {
  const router = useRouter();
  const [activeFilter, setActiveFilter] = useState("All");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const filters = ["All", "Fed/RBI", "Crude", "Geopolitical", "Trade", "Crypto"];

  const { data: eventsData } = useQuery({
    queryKey: ['events'],
    queryFn: () => fetchEvents(),
  });

  const { data: eventImpact, isFetching: isImpactFetching } = useQuery({
    queryKey: ['event_impact', selectedEventId],
    queryFn: () => fetchEventImpact(selectedEventId!),
    enabled: !!selectedEventId
  });

  const getSeverityColor = (severity: string | null) => {
    switch (severity) {
      case 'High': return 'bg-tv-red';
      case 'Medium': return 'bg-amber';
      default: return 'bg-teal';
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full p-4">
      {/* LEFT PANE (60%) */}
      <div className="flex-[6] flex flex-col bg-bg-secondary border border-border-dark rounded-xl overflow-hidden h-full">
        {/* Filters */}
        <div className="h-12 flex items-center px-2 border-b border-border-dark flex-shrink-0">
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`text-sm px-3 py-1.5 rounded transition-colors ${activeFilter === f ? 'bg-bg-tertiary text-text-primary font-medium' : 'text-text-secondary hover:text-text-primary'}`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Events List */}
        <div className="flex-1 overflow-y-auto">
          {!eventsData?.events?.length && (
            <div className="p-8 text-center text-text-secondary text-sm">No events available.</div>
          )}
          {eventsData?.events?.map((ev) => (
            <div 
              key={ev.id}
              onClick={() => setSelectedEventId(ev.id)}
              className={`flex items-start gap-3 p-4 border-b border-border-dark/50 cursor-pointer transition-colors ${selectedEventId === ev.id ? 'bg-bg-tertiary' : 'hover:bg-bg-tertiary/50'}`}
            >
              <div className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${getSeverityColor(ev.severity)} shadow-[0_0_8px_currentColor]`} />
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start mb-1">
                  <h3 className={`font-semibold ${selectedEventId === ev.id ? 'text-text-primary' : 'text-text-primary/90'}`}>
                    {ev.headline}
                  </h3>
                  <span className="text-xs text-text-secondary whitespace-nowrap ml-4">{ev.timestamp}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-secondary">{ev.source}</span>
                  <div className="flex gap-1.5">
                    {ev.sectors?.map((s) => (
                      <span key={s} className="text-[10px] bg-bg-primary border border-border-light text-text-secondary px-1.5 py-0.5 rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT PANE (40%) */}
      <div className="flex-[4] flex flex-col bg-bg-secondary border border-border-dark rounded-xl overflow-hidden h-full">
        {!selectedEventId ? (
          <div className="flex-1 flex items-center justify-center text-text-secondary flex-col gap-2">
            <span className="material-symbols-outlined text-4xl opacity-50">feed</span>
            <p>Select an event to view macro impact</p>
          </div>
        ) : isImpactFetching ? (
          <div className="flex-1 flex items-center justify-center text-text-secondary">
            Loading impact mapping...
          </div>
        ) : (
          <div className="flex flex-col h-full overflow-y-auto">
            {/* Header */}
            <div className="p-4 border-b border-border-dark bg-bg-tertiary/30">
              <div className="flex items-center gap-2 mb-2">
                {eventImpact?.severity && (
                  <span className={`px-2 py-0.5 text-xs font-bold rounded ${getSeverityColor(eventImpact.severity)} text-white bg-opacity-20`}>
                    {eventImpact.severity} IMPACT
                  </span>
                )}
              </div>
              <h2 className="text-xl font-bold text-text-primary mb-2">{eventImpact?.title}</h2>
              <p className="text-sm text-text-secondary leading-relaxed">
                {eventImpact?.ai_analysis}
              </p>
            </div>

            {/* Impact Diagram (SVG Animated) */}
            <div className="p-6 border-b border-border-dark relative flex justify-center bg-bg-primary">
              <svg width="240" height="180" viewBox="0 0 240 180" className="opacity-90">
                {/* Lines */}
                <motion.path d="M 120 20 L 120 60" stroke="#363A45" strokeWidth="2" fill="none" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: 0.1 }} />
                <motion.path d="M 120 80 L 60 130" stroke="#EF5350" strokeWidth="2" strokeDasharray="4 4" fill="none" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: 0.4 }} />
                <motion.path d="M 120 80 L 180 130" stroke="#26A69A" strokeWidth="2" strokeDasharray="4 4" fill="none" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: 0.4 }} />
                
                {/* Nodes */}
                <motion.rect x="70" y="0" width="100" height="30" rx="4" fill="#1E222D" stroke="#0EA5C9" strokeWidth="2" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.3 }} />
                <text x="120" y="19" textAnchor="middle" fill="#D1D4DC" fontSize="12" fontWeight="600">Macro Event</text>
                
                <motion.rect x="70" y="60" width="100" height="30" rx="4" fill="#1E222D" stroke="#363A45" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.3, delay: 0.3 }} />
                <text x="120" y="79" textAnchor="middle" fill="#787B86" fontSize="10">Chain Reaction</text>
                
                <motion.rect x="10" y="130" width="100" height="30" rx="4" fill="#EF5350" fillOpacity="0.1" stroke="#EF5350" strokeWidth="1" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.3, delay: 0.6 }} />
                <text x="60" y="149" textAnchor="middle" fill="#EF5350" fontSize="12" fontWeight="600">Pressure</text>
                
                <motion.rect x="130" y="130" width="100" height="30" rx="4" fill="#26A69A" fillOpacity="0.1" stroke="#26A69A" strokeWidth="1" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.3, delay: 0.6 }} />
                <text x="180" y="149" textAnchor="middle" fill="#26A69A" fontSize="12" fontWeight="600">Beneficiaries</text>
                
                {/* Pulses */}
                <motion.circle cx="120" cy="15" r="4" fill="#0EA5C9" animate={{ scale: [1, 2, 1], opacity: [1, 0, 1] }} transition={{ duration: 2, repeat: Infinity }} />
              </svg>
            </div>

            {/* Affected Stocks */}
            <div className="flex-1 p-4 grid grid-cols-2 gap-4">
              {/* Bullish */}
              <div>
                <h3 className="text-xs font-bold text-tv-green mb-3 uppercase tracking-wider">Beneficiaries</h3>
                <div className="space-y-2">
                  {eventImpact?.stocks?.beneficiaries?.map((b, i) => (
                    <div key={i} className="p-3 bg-bg-primary border border-border-dark rounded hover:border-tv-green cursor-pointer transition-colors" onClick={() => router.push(`/symbol/${b.ticker}`)}>
                      <div className="font-bold text-text-primary mb-1">{b.ticker}</div>
                      <div className="text-xs text-text-secondary leading-tight">{b.reason}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bearish */}
              <div>
                <h3 className="text-xs font-bold text-tv-red mb-3 uppercase tracking-wider">Pressure</h3>
                <div className="space-y-2">
                  {eventImpact?.stocks?.pressure?.map((p, i) => (
                    <div key={i} className="p-3 bg-bg-primary border border-border-dark rounded hover:border-tv-red cursor-pointer transition-colors" onClick={() => router.push(`/symbol/${p.ticker}`)}>
                      <div className="font-bold text-text-primary mb-1">{p.ticker}</div>
                      <div className="text-xs text-text-secondary leading-tight">{p.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Action */}
            <div className="p-4 border-t border-border-dark mt-auto">
              <button 
                onClick={() => router.push("/picks")}
                className="w-full bg-teal text-text-white font-semibold py-2.5 rounded hover:bg-teal/90 transition-colors"
              >
                Get AI Picks for this Event
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
