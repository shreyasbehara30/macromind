"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { User, Session } from "@supabase/supabase-js";
import { useRouter, usePathname } from "next/navigation";

type AuthContextType = {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  setDemoSession: (name: string, email: string) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  isLoading: true,
  setDemoSession: () => {},
  logout: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const setDemoSession = (name: string, email: string) => {
    const demoUser: User = {
      id: "user_" + Math.random().toString(36).substring(2, 9),
      app_metadata: { provider: "email" },
      user_metadata: { full_name: name || "User" },
      aud: "authenticated",
      created_at: new Date().toISOString(),
      email: email || "trader@macromind.ai",
      phone: "",
      role: "authenticated",
      updated_at: new Date().toISOString(),
    };
    const demoSession: Session = {
      access_token: "demo-token-" + Date.now(),
      token_type: "bearer",
      expires_in: 86400,
      refresh_token: "demo-refresh-token",
      user: demoUser,
    };
    if (typeof window !== "undefined") {
      localStorage.setItem("macromind_local_session", JSON.stringify(demoSession));
    }
    setUser(demoUser);
    setSession(demoSession);
  };

  const logout = async () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("macromind_local_session");
    }
    setUser(null);
    setSession(null);
    try {
      await supabase.auth.signOut();
    } catch (e) {
      // ignore
    }
    router.push("/auth/login");
  };

  useEffect(() => {
    let localSess: Session | null = null;
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("macromind_local_session");
      if (stored) {
        try {
          localSess = JSON.parse(stored);
        } catch (e) {}
      }
    }

    if (localSess) {
      setSession(localSess);
      setUser(localSess.user);
      setIsLoading(false);
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, supabaseSession) => {
      if (supabaseSession) {
        setSession(supabaseSession);
        setUser(supabaseSession.user);
      } else if (!localSess) {
        setSession(null);
        setUser(null);
      }
      setIsLoading(false);

      const activeUser = supabaseSession?.user || localSess?.user;
      const isProtectedRoute = ["/dashboard", "/events", "/picks", "/watchlist", "/paper"].some(route => pathname?.startsWith(route));
      if (!activeUser && isProtectedRoute) {
        router.push("/auth/login");
      }
    });

    return () => subscription.unsubscribe();
  }, [pathname, router]);

  return (
    <AuthContext.Provider value={{ user, session, isLoading, setDemoSession, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

