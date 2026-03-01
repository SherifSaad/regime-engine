/**
 * Twelve Data API client (server-side only).
 * Phase 1: Quote + Logo for per-asset pages.
 */

const BASE = "https://api.twelvedata.com"

const PROVIDER_SYMBOLS: Record<string, string> = {
  EURUSD: "EUR/USD",
  GBPUSD: "GBP/USD",
  AUDUSD: "AUD/USD",
  USDJPY: "USD/JPY",
  USDCAD: "USD/CAD",
  BTCUSD: "BTC/USD",
  ETHUSD: "ETH/USD",
  BNBUSD: "BNB/USD",
  XRPUSD: "XRP/USD",
  ADAUSD: "ADA/USD",
  SOLUSD: "SOL/USD",
  DOGEUSD: "DOGE/USD",
  AVAXUSD: "AVAX/USD",
  LINKUSD: "LINK/USD",
  TONUSD: "TON/USD",
  XAUUSD: "XAU/USD",
  XAGUSD: "XAG/USD",
  XPTUSD: "XPT/USD",
  XBRUSD: "XBR/USD",
  WTIUSD: "WTI/USD",
  NGUSD: "NG/USD",
  HGUSD: "HG/USD",
  ZCUSD: "ZC/USD",
}

function toProviderSymbol(symbol: string): string {
  const upper = symbol.toUpperCase()
  return PROVIDER_SYMBOLS[upper] ?? upper
}

function getApiKey(): string {
  const key = process.env.TWELVEDATA_API_KEY?.trim()
  if (!key) return ""
  return key
}

export type QuoteData = {
  close: string
  open: string
  high: string
  low: string
  volume: string
  change: string
  percent_change: string
}

export type LogoData = {
  url?: string
  logo_base?: string
  logo_quote?: string
}

export type ProfileData = {
  description?: string
  sector?: string
  industry?: string
}

export type StatisticsData = {
  market_cap?: number
  pe?: number
  fifty_two_week_high?: number
  fifty_two_week_low?: number
  dividend_yield?: number
}

export type EarningsData = {
  next_date?: string
  next_time?: string
  last_date?: string
  last_eps_estimate?: number
  last_eps_actual?: number
  last_surprise_prc?: number
}

export type AnalystData = {
  strong_buy?: number
  buy?: number
  hold?: number
  sell?: number
  strong_sell?: number
  rating?: number
  price_target_high?: number
  price_target_median?: number
  price_target_low?: number
  price_target_average?: number
  price_target_current?: number
}

async function fetchJson<T>(
  path: string,
  params: Record<string, string>
): Promise<T | null> {
  const key = getApiKey()
  if (!key) return null

  const search = new URLSearchParams({ ...params, apikey: key })
  const url = `${BASE}${path}?${search}`

  try {
    const res = await fetch(url, { next: { revalidate: 60 } })
    if (!res.ok) return null
    const data = (await res.json()) as Record<string, unknown>
    if (data.status === "error" || data.code) return null
    return data as T
  } catch {
    return null
  }
}

export async function getQuote(symbol: string): Promise<QuoteData | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    close?: string
    open?: string
    high?: string
    low?: string
    volume?: string
    change?: string
    percent_change?: string
  }>("/quote", { symbol: tdSymbol })

  if (!data?.close) return null

  return {
    close: data.close ?? "",
    open: data.open ?? "",
    high: data.high ?? "",
    low: data.low ?? "",
    volume: data.volume ?? "",
    change: data.change ?? "",
    percent_change: data.percent_change ?? "",
  }
}

export async function getLogo(symbol: string): Promise<LogoData | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    url?: string
    logo_base?: string
    logo_quote?: string
  }>("/logo", { symbol: tdSymbol })

  if (!data) return null

  return {
    url: data.url,
    logo_base: data.logo_base,
    logo_quote: data.logo_quote,
  }
}

export async function getProfile(symbol: string): Promise<ProfileData | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    description?: string
    sector?: string
    industry?: string
  }>("/profile", { symbol: tdSymbol })

  if (!data) return null

  return {
    description: data.description,
    sector: data.sector,
    industry: data.industry,
  }
}

export async function getStatistics(
  symbol: string
): Promise<StatisticsData | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    statistics?: {
      valuations_metrics?: { market_capitalization?: number; trailing_pe?: number }
      stock_price_summary?: {
        fifty_two_week_high?: number
        fifty_two_week_low?: number
      }
      dividends_and_splits?: {
        forward_annual_dividend_yield?: number
        trailing_annual_dividend_yield?: number
      }
    }
  }>("/statistics", { symbol: tdSymbol })

  const stats = data?.statistics
  if (!stats) return null

  const valuations = stats.valuations_metrics
  const priceSummary = stats.stock_price_summary
  const div = stats.dividends_and_splits
  const yieldPct =
    div?.forward_annual_dividend_yield ?? div?.trailing_annual_dividend_yield

  return {
    market_cap: valuations?.market_capitalization,
    pe: valuations?.trailing_pe,
    fifty_two_week_high: priceSummary?.fifty_two_week_high,
    fifty_two_week_low: priceSummary?.fifty_two_week_low,
    dividend_yield: yieldPct != null ? yieldPct * 100 : undefined,
  }
}

export async function getEarnings(symbol: string): Promise<EarningsData | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    earnings?: Array<{
      date?: string
      time?: string
      eps_estimate?: number
      eps_actual?: number
      surprise_prc?: number
    }>
  }>("/earnings", { symbol: tdSymbol })

  const list = data?.earnings
  if (!Array.isArray(list) || list.length === 0) return null

  const today = new Date().toISOString().slice(0, 10)
  let next: (typeof list)[0] | undefined
  let last: (typeof list)[0] | undefined

  for (const e of list) {
    const d = e.date ?? ""
    if (!d) continue
    if (e.eps_actual != null) {
      if (!last || d > (last.date ?? "")) last = e
    } else if (d >= today) {
      if (!next || d < (next.date ?? "9999")) next = e
    }
  }

  if (!next && !last) return null

  return {
    next_date: next?.date,
    next_time: next?.time,
    last_date: last?.date,
    last_eps_estimate: last?.eps_estimate,
    last_eps_actual: last?.eps_actual,
    last_surprise_prc: last?.surprise_prc,
  }
}

export async function getRecommendations(
  symbol: string
): Promise<Pick<
  AnalystData,
  "strong_buy" | "buy" | "hold" | "sell" | "strong_sell" | "rating"
> | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    trends?: { current_month?: Record<string, number> }
    rating?: number
  }>("/recommendations", { symbol: tdSymbol })

  const curr = data?.trends?.current_month
  if (!curr) return null

  return {
    strong_buy: curr.strong_buy,
    buy: curr.buy,
    hold: curr.hold,
    sell: curr.sell,
    strong_sell: curr.strong_sell,
    rating: data?.rating,
  }
}

export async function getPriceTarget(
  symbol: string
): Promise<Pick<
  AnalystData,
  | "price_target_high"
  | "price_target_median"
  | "price_target_low"
  | "price_target_average"
  | "price_target_current"
> | null> {
  const tdSymbol = toProviderSymbol(symbol)
  const data = await fetchJson<{
    price_target?: {
      high?: number
      median?: number
      low?: number
      average?: number
      current?: number
    }
  }>("/price_target", { symbol: tdSymbol })

  const pt = data?.price_target
  if (!pt) return null

  return {
    price_target_high: pt.high,
    price_target_median: pt.median,
    price_target_low: pt.low,
    price_target_average: pt.average,
    price_target_current: pt.current,
  }
}

/** Fetches logo, profile, statistics, earnings, analyst — NOT quote/price (use market cache). */
export async function getLogoProfileStatsWithoutQuote(symbol: string): Promise<{
  logo: LogoData | null
  profile: ProfileData | null
  statistics: StatisticsData | null
  earnings: EarningsData | null
  analyst: AnalystData | null
}> {
  const [logo, profile, statistics, earnings, recs, pt] = await Promise.all([
    getLogo(symbol),
    getProfile(symbol),
    getStatistics(symbol),
    getEarnings(symbol),
    getRecommendations(symbol),
    getPriceTarget(symbol),
  ])

  const analyst: AnalystData | null = recs || pt ? { ...recs, ...pt } : null

  return { logo, profile, statistics, earnings, analyst }
}

export async function getQuoteLogoProfileStats(symbol: string): Promise<{
  quote: QuoteData | null
  logo: LogoData | null
  profile: ProfileData | null
  statistics: StatisticsData | null
  earnings: EarningsData | null
  analyst: AnalystData | null
}> {
  const [quote, logo, profile, statistics, earnings, recs, pt] =
    await Promise.all([
      getQuote(symbol),
      getLogo(symbol),
      getProfile(symbol),
      getStatistics(symbol),
      getEarnings(symbol),
      getRecommendations(symbol),
      getPriceTarget(symbol),
    ])

  const analyst: AnalystData | null =
    recs || pt
      ? { ...recs, ...pt }
      : null

  return {
    quote,
    logo,
    profile,
    statistics,
    earnings,
    analyst,
  }
}
