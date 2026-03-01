export type AssetItem = {
  symbol: string
  name: string
  asset_class: string
  has_compute?: boolean
}

const DISPLAY_NAMES: Record<string, string> = {
  US_EQUITY_INDEX: "Indices",
  US_EQUITY: "Equities",
  CRYPTO: "Crypto",
  Commodities: "Commodities",
  "Fixed Income": "Rates",
  FX: "FX",
}

export function assetClassDisplayName(ac: string): string {
  return DISPLAY_NAMES[ac] ?? ac
}

const CRYPTO_SYMBOLS = new Set([
  "BTCUSD", "ETHUSD", "BNBUSD", "XRPUSD", "ADAUSD", "SOLUSD", "DOGEUSD",
  "AVAXUSD", "LINKUSD", "TONUSD", "ADAUSD", "MATICUSD", "DOTUSD", "SHIBUSD",
])
const FX_SYMBOLS = new Set(["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD"])
const COMMODITY_SYMBOLS = new Set(["XAUUSD", "XAGUSD", "XPTUSD", "XBRUSD", "WTIUSD", "NGUSD", "HGUSD", "ZCUSD", "GC", "SI"])

export function normalizeAssetClassForSymbol(symbol: string, fromApi: string | undefined): string {
  if (fromApi) return fromApi
  const upper = symbol.toUpperCase()
  if (CRYPTO_SYMBOLS.has(upper)) return "CRYPTO"
  if (FX_SYMBOLS.has(upper)) return "FX"
  if (COMMODITY_SYMBOLS.has(upper)) return "Commodities"
  return "US_EQUITY"
}
