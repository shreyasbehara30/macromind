/**
 * Per-user identity for the paper backend (watchlist, paper trading).
 *
 * The backend keys all personal data by the X-Session-Id header and falls
 * back to a single shared mock identity when it is absent (which is why
 * every user currently shares one watchlist). AuthProvider sets the id from
 * whoever is signed in; api.ts attaches it to every request.
 *
 * Demo-session ids are stable per email (not random per login), so signing
 * out and back in returns the same watchlist and portfolio.
 */

const STORAGE_KEY = "macromind_session_id";

let cached: string | null = null;

function hashEmail(email: string): string {
  let h = 5381;
  const s = email.trim().toLowerCase();
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  }
  return h.toString(36);
}

/** Stable session id for a demo (non-Supabase) login. */
export function stableIdForEmail(email: string): string {
  return `demo_${hashEmail(email || "trader@macromind.ai")}`;
}

export function setSessionId(id: string | null): void {
  cached = id;
  try {
    if (typeof window !== "undefined") {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // storage unavailable; module cache still works for this page lifetime
  }
}

export function getSessionId(): string | null {
  if (cached) return cached;
  try {
    if (typeof window !== "undefined") {
      cached = localStorage.getItem(STORAGE_KEY);
    }
  } catch {
    // ignore
  }
  return cached;
}
