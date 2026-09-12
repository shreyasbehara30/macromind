"use client";

import { useAuth } from "./AuthProvider";
import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

export default function MainLayoutWrapper({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  
  if (!user) {
    return (
      <main className="flex flex-col min-h-screen w-full relative bg-bg-primary">
        {children}
      </main>
    );
  }

  return (
    <div className="flex flex-col h-screen w-full bg-bg-primary overflow-hidden text-text-primary">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto relative flex flex-col">
          {children}
        </main>
      </div>
    </div>
  );
}
