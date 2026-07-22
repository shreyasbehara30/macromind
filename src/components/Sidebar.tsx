"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { supabase } from "@/lib/supabase";

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const navSections = [
    {
      title: "MARKETS",
      items: [
        { name: "Dashboard", href: "/dashboard", icon: "dashboard" },
        { name: "Live Events", href: "/events", icon: "feed" },
        { name: "AI Picks", href: "/picks", icon: "model_training" },
      ]
    },
    {
      title: "PORTFOLIO",
      items: [
        { name: "Watchlist", href: "/watchlist", icon: "monitoring" },
        { name: "Paper Portfolio", href: "/paper", icon: "account_balance_wallet" },
      ]
    }
  ];

  return (
    <div className="w-[240px] h-full bg-bg-secondary border-r border-border-dark flex flex-col flex-shrink-0">
      
      {/* Brand */}
      <div className="h-12 flex items-center px-4 border-b border-border-dark">
        <Link href="/dashboard" className="flex items-center gap-2 group">
          <div className="w-6 h-6 rounded bg-teal flex items-center justify-center">
            <span className="material-symbols-outlined text-text-white text-sm">language</span>
          </div>
          <span className="font-bold tracking-wider text-text-primary text-sm">MacroMind</span>
        </Link>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-4">
        {navSections.map((section) => (
          <div key={section.title} className="mb-4">
            <div 
              className="px-4 py-1 flex items-center justify-between cursor-pointer group"
              onClick={() => toggleSection(section.title)}
            >
              <span className="text-xs font-semibold text-text-secondary tracking-wider group-hover:text-text-primary transition-colors">
                {section.title}
              </span>
              <span className="material-symbols-outlined text-text-secondary text-[16px] group-hover:text-text-primary transition-colors">
                {collapsedSections[section.title] ? 'expand_more' : 'expand_less'}
              </span>
            </div>
            
            <AnimatePresence initial={false}>
              {!collapsedSections[section.title] && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="mt-1 space-y-[2px]">
                    {section.items.map((item) => {
                      const isActive = pathname === item.href;
                      return (
                        <Link
                          key={item.name}
                          href={item.href}
                          className={`relative flex items-center gap-3 px-4 py-1.5 transition-colors ${
                            isActive 
                              ? "bg-teal/10 text-text-primary" 
                              : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                          }`}
                        >
                          {isActive && (
                            <motion.div
                              layoutId="activeNav"
                              className="absolute left-0 top-0 bottom-0 w-[3px] bg-teal"
                              transition={{ type: "spring", stiffness: 300, damping: 30 }}
                            />
                          )}
                          <span className="material-symbols-outlined text-[18px]">
                            {item.icon}
                          </span>
                          <span className="text-sm font-medium">{item.name}</span>
                        </Link>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>

      {/* User Profile */}
      <div className="p-4 border-t border-border-dark flex items-center justify-between">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="w-8 h-8 rounded bg-bg-tertiary border border-border-light flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-medium text-text-primary">
              {user?.user_metadata?.full_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
            </span>
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-text-primary truncate">
              {user?.user_metadata?.full_name || 'User'}
            </span>
            <span className="text-xs text-text-secondary truncate">
              {user?.email}
            </span>
          </div>
        </div>
        <button 
          onClick={() => logout()}
          className="material-symbols-outlined text-text-secondary hover:text-tv-red transition-colors text-[20px]"
          title="Sign Out"
        >
          logout
        </button>
      </div>

    </div>
  );
}
