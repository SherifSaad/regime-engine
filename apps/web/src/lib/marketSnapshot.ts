/**
 * Market snapshot from internal cache (market_latest).
 * Price, Change %, Volume read from this layer — never Twelve Data at request time.
 */
import { getMarketLatestMap } from "./marketCacheDb"

export type MarketRealtimeRow = {
  symbol: string
  price: number | null
  change_pct: number | null
  volume: number | null
  day_range_low?: number | null
  day_range_high?: number | null
  market_cap?: number | null
  next_earnings_date?: string | null
}

/** Reads from market_latest SQLite cache (populated by market_cache service). */
export function getMarketRealtimeLatest(): Record<string, MarketRealtimeRow> {
  const rows = getMarketLatestMap()
  const out: Record<string, MarketRealtimeRow> = {}
  for (const [symbol, r] of Object.entries(rows)) {
    out[symbol] = {
      symbol: r.symbol,
      price: r.price,
      change_pct: r.change_pct,
      volume: r.volume,
      day_range_low: r.day_low,
      day_range_high: r.day_high,
      market_cap: r.market_cap,
      next_earnings_date: r.next_earnings_date,
    }
  }
  return out
}
