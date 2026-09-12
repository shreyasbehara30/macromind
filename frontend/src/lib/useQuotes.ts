"use client";

import { useQueries } from "@tanstack/react-query";
import { fetchQuote, type Market, type Quote } from "@/lib/api";

export interface QuoteKey {
  ticker: string;
  market: Market;
}

export type QuoteMap = Map<string, Quote>;

export const quoteKey = (market: string, ticker: string) => `${market}:${ticker}`;

/**
 * Fetch quotes for many symbols in parallel.
 *
 * One request per symbol, issued concurrently by react-query rather than in a
 * sequential await loop. There is no batch endpoint on the backend and adding
 * one was out of scope, so parallel single fetches is the available option.
 *
 * A symbol whose quote fails is simply absent from the returned map. Callers
 * must render that absence as unknown. Never substitute another number for a
 * missing mark: an entry price standing in for a live price renders a 0.00 P&L
 * that looks real.
 */
export function useQuotes(items: QuoteKey[]) {
  const results = useQueries({
    queries: items.map((item) => ({
      queryKey: ["quote", item.market, item.ticker],
      queryFn: () => fetchQuote(item.market, item.ticker),
      refetchInterval: 15000,
      // A missing quote is a normal outcome, not something to hammer.
      retry: 1,
      staleTime: 10000,
    })),
  });

  const quotes: QuoteMap = new Map();
  results.forEach((result, i) => {
    if (result.data && typeof result.data.price === "number" && result.data.price > 0) {
      quotes.set(quoteKey(items[i].market, items[i].ticker), result.data);
    }
  });

  return {
    quotes,
    isLoading: results.some((r) => r.isLoading),
    // True only when every symbol failed and at least one was requested.
    allFailed: items.length > 0 && results.every((r) => r.isError),
  };
}
