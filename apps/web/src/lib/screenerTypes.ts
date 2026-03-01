/**
 * Stable row shape for screener table.
 * Merged from assets + market snapshot + regime (placeholders OK).
 */

export type ScreenerRow = {
  symbol: string
  asset_class: string
  price: number | null
  change_pct: number | null
  volume: number | null
  market_cap: number | null
  next_earnings_date: string | null
  regime_state: string | null
  escalation_pct: number | null
  trend_strength: number | null
}
