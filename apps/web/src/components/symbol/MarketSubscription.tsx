"use client"

import { useEffect } from "react"

/** Reports symbol to market_cache for WebSocket streaming when viewing asset page. */
export function MarketSubscription({ symbol }: { symbol: string }) {
  useEffect(() => {
    if (!symbol) return
    fetch("/api/market-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: [symbol] }),
    }).catch(() => {})
  }, [symbol])
  return null
}
