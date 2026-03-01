/**
 * Symbol mapping for Twelve Data (FX, Crypto use different formats).
 */
export const PROVIDER_SYMBOLS = {
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

export function toProviderSymbol(symbol) {
  const upper = String(symbol).toUpperCase()
  return PROVIDER_SYMBOLS[upper] ?? upper
}
