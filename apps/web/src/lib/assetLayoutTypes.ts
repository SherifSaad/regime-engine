import type {
  QuoteData,
  LogoData,
  ProfileData,
  StatisticsData,
  EarningsData,
  AnalystData,
} from "./twelvedata"
import type { RegimeState } from "./metrics"

export type AssetLayoutProps = {
  symbol: string
  name: string
  assetClass?: string
  quote?: QuoteData | null
  marketCap?: number | null
  nextEarningsDate?: string | null
  logo?: LogoData | null
  profile?: ProfileData | null
  statistics?: StatisticsData | null
  earnings?: EarningsData | null
  analyst?: AnalystData | null
  /** When true, regime/metrics data is shown; when false, blurred for free users */
  isPaid?: boolean
  /** Per-timeframe regime state (when available from compute) */
  regimeByTf?: Record<string, RegimeState>
}
