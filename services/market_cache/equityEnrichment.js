/**
 * Fetch market_cap and next_earnings_date for equities from Twelve Data.
 * Called on a separate daily interval.
 */
import { toProviderSymbol } from "./symbolMap.js"

const BASE = "https://api.twelvedata.com"

function getApiKey() {
  return process.env.TWELVEDATA_API_KEY?.trim() || ""
}

async function fetchJson(path, params) {
  const key = getApiKey()
  if (!key) return null
  const search = new URLSearchParams({ ...params, apikey: key })
  const url = `${BASE}${path}?${search}`
  try {
    const res = await fetch(url)
    if (!res.ok) return null
    const data = await res.json()
    if (data.status === "error" || data.code) return null
    return data
  } catch {
    return null
  }
}

export async function fetchStatistics(symbol, providerMap = {}) {
  const tdSymbol = providerMap[symbol] || toProviderSymbol(symbol)
  const data = await fetchJson("/statistics", { symbol: tdSymbol })
  const stats = data?.statistics
  if (!stats) return null
  const mc = stats.valuations_metrics?.market_capitalization
  return mc != null ? Number(mc) : null
}

export async function fetchEarningsNextDate(symbol, providerMap = {}) {
  const tdSymbol = providerMap[symbol] || toProviderSymbol(symbol)
  const data = await fetchJson("/earnings", { symbol: tdSymbol })
  const list = data?.earnings
  if (!Array.isArray(list) || list.length === 0) return null
  const today = new Date().toISOString().slice(0, 10)
  let next = null
  for (const e of list) {
    const d = e.date ?? ""
    if (!d) continue
    if (e.eps_actual == null && d >= today) {
      if (!next || d < next) next = d
    }
  }
  return next
}
