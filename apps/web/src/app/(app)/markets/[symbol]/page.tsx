import { LayoutEquities } from "@/components/symbol/LayoutEquities"
import { LayoutFX } from "@/components/symbol/LayoutFX"
import { MarketSubscription } from "@/components/symbol/MarketSubscription"
import { LayoutCrypto } from "@/components/symbol/LayoutCrypto"
import { LayoutCommodities } from "@/components/symbol/LayoutCommodities"
import { LayoutFixedIncome } from "@/components/symbol/LayoutFixedIncome"
import { riApi } from "@/lib/api"
import { normalizeAssetClassForSymbol } from "@/lib/assetTypes"
import { getLogoProfileStatsWithoutQuote } from "@/lib/twelvedata"
import { getMarketLatestBySymbol } from "@/lib/marketCacheDb"
import type { QuoteData, LogoData, ProfileData, StatisticsData, EarningsData, AnalystData } from "@/lib/twelvedata"
import type { AssetLayoutProps } from "@/lib/assetLayoutTypes"

const LAYOUT_MAP: Record<string, React.ComponentType<AssetLayoutProps>> = {
  US_EQUITY: LayoutEquities,
  US_EQUITY_INDEX: LayoutEquities,
  FX: LayoutFX,
  CRYPTO: LayoutCrypto,
  Commodities: LayoutCommodities,
  "Fixed Income": LayoutFixedIncome,
}

export default async function SymbolPage({
  params,
}: {
  params: Promise<{ symbol: string }>
}) {
  const { symbol } = await params
  let asset
  try {
    asset = await riApi.asset(symbol)
  } catch {
    asset = null
  }

  const ac = normalizeAssetClassForSymbol(symbol, asset?.asset_class)
  const Layout = LAYOUT_MAP[ac] ?? LayoutEquities
  const name = asset?.name ?? symbol

  let quote: QuoteData | null = null
  const cache = getMarketLatestBySymbol(symbol.toUpperCase())
  if (cache?.price != null) {
    quote = {
      close: String(cache.price),
      open: "",
      high: cache.day_high != null ? String(cache.day_high) : "",
      low: cache.day_low != null ? String(cache.day_low) : "",
      volume: cache.volume != null ? String(cache.volume) : "",
      change: "",
      percent_change: cache.change_pct != null ? String(cache.change_pct) : "",
    }
  }

  let logo: LogoData | null = null
  let profile: ProfileData | null = null
  let statistics: StatisticsData | null = null
  let earnings: EarningsData | null = null
  let analyst: AnalystData | null = null
  try {
    const data = await getLogoProfileStatsWithoutQuote(symbol)
    logo = data.logo
    profile = data.profile
    statistics = data.statistics
    earnings = data.earnings
    analyst = data.analyst
  } catch {
    // Twelve Data unavailable for profile/earnings/analyst
  }

  return (
    <>
      <MarketSubscription symbol={symbol.toUpperCase()} />
      <Layout
      symbol={symbol.toUpperCase()}
      name={name}
      assetClass={ac}
      quote={quote}
      marketCap={cache?.market_cap ?? null}
      nextEarningsDate={cache?.next_earnings_date ?? null}
      logo={logo}
      profile={profile}
      statistics={statistics}
      earnings={earnings}
      analyst={analyst}
      isPaid={asset?.has_compute ?? false}
      regimeByTf={{}}
    />
    </>
  )
}
