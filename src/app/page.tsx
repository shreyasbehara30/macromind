"use client";

import Link from "next/link";
import { motion } from "framer-motion";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface flex flex-col relative overflow-hidden">
      {/* Animated CSS Grid Background */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center opacity-30">
        <div className="w-[200%] h-[200%] bg-[linear-gradient(rgba(14,165,201,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(14,165,201,0.1)_1px,transparent_1px)] bg-[size:40px_40px] [transform:perspective(500px)_rotateX(60deg)_translateY(-100px)_translateZ(-200px)] animate-[grid_20s_linear_infinite]"></div>
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes grid {
          0% { transform: perspective(500px) rotateX(60deg) translateY(0px) translateZ(-200px); }
          100% { transform: perspective(500px) rotateX(60deg) translateY(40px) translateZ(-200px); }
        }
      `}} />

      <main className="flex-1 flex flex-col items-center justify-center z-10 px-4">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-center max-w-3xl"
        >
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/30 flex items-center justify-center shadow-[0_0_30px_rgba(14,165,201,0.4)]">
              <span className="material-symbols-outlined text-primary text-5xl">dashboard</span>
            </div>
          </div>
          <h1 className="text-5xl md:text-7xl font-bold text-text-primary mb-6 tracking-tight">
            Intelligence for the <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">Modern Markets</span>
          </h1>
          <p className="text-xl text-text-secondary mb-10 max-w-2xl mx-auto leading-relaxed">
            AI-driven macro event analysis, predictive portfolio impact, and a paper trading environment to test your thesis.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/auth/signup" className="w-full sm:w-auto px-8 py-3 rounded-full bg-primary text-on-primary font-medium hover:bg-primary/90 transition-all hover:scale-105 shadow-[0_0_20px_rgba(14,165,201,0.3)]">
              Get Started Free
            </Link>
            <Link href="/auth/login" className="w-full sm:w-auto px-8 py-3 rounded-full glass-card text-text-primary font-medium hover:bg-surface-container transition-all">
              Sign In
            </Link>
          </div>
        </motion.div>

        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl w-full">
          {[
            { icon: "event", title: "Live Macro Events", desc: "Real-time AI classification of global economic events and their severity." },
            { icon: "auto_awesome", title: "AI Agents", desc: "Deep impact analysis predicting beneficiary and at-risk assets instantly." },
            { icon: "account_balance_wallet", title: "Paper Trading", desc: "Test strategies safely with a virtual portfolio running on live data." },
          ].map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.6 + i * 0.1 }}
              className="glass-card p-6 rounded-2xl text-center"
            >
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <span className="material-symbols-outlined text-primary">{feature.icon}</span>
              </div>
              <h3 className="text-lg font-bold text-text-primary mb-2">{feature.title}</h3>
              <p className="text-sm text-text-secondary">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}
