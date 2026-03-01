/**
 * Twelve Data API client for market cache.
 * Batch quote + WebSocket streaming.
 */
import { PROVIDER_SYMBOLS, toProviderSymbol } from "./symbolMap.js"

const BASE = "https://api.twelvedata.com"

function reverseSymbol(tdSymbol) {
  const normalized = String(tdSymbol || "").replace("/", "")
  const entry = Object.entries(PROVIDER_SYMBOLS).find(([, v]) => v === tdSymbol || v.replace("/", "") === normalized)
  return entry ? entry[0] : (normalized.includes("USD") ? normalized : null)
}
const WS_BASE = "wss://api.twelvedata.com/v1/quotes"

function getApiKey() {
  const key = process.env.TWELVEDATA_API_KEY?.trim()
  return key || ""
}

/**
 * Fetch quote for multiple symbols (comma-separated).
 * Twelve Data supports batch: symbol=AAPL,MSFT,EUR/USD
 * Max ~120 symbols per request; we chunk to 30 to avoid limits.
 */
const SINGLE_DELAY_MS = parseInt(process.env.MARKET_CACHE_SINGLE_DELAY_MS || "10000", 10)

export async function fetchBatchQuotes(symbols, providerMap = {}) {
  const key = getApiKey()
  if (!key) return []

  const useSingleOnly = process.env.MARKET_CACHE_SINGLE_ONLY === "1" || process.env.MARKET_CACHE_SINGLE_ONLY === "true"
  let rateLimitRetries = 0
  const MAX_RATE_LIMIT_RETRIES = 1

  const CHUNK = useSingleOnly ? 1 : 5
  const results = []

  for (let i = 0; i < symbols.length; i += CHUNK) {
    const chunk = symbols.slice(i, i + CHUNK)
    const tdSymbols = chunk.map((s) => providerMap[s] || toProviderSymbol(s))
    const symbolParam = tdSymbols.join(",")

    try {
      const url = `${BASE}/quote?symbol=${encodeURIComponent(symbolParam)}&apikey=${key}`
      const res = await fetch(url)
      const data = await res.json()

      if (res.status === 429 || (data.status === "error" && /rate|credit|limit/i.test(String(data.message || "")))) {
        rateLimitRetries++
        if (rateLimitRetries > MAX_RATE_LIMIT_RETRIES) {
          console.warn(`[market_cache] Rate limit hit, switching to single-symbol mode (${SINGLE_DELAY_MS}ms delay)...`)
          return fetchSingleOnly(symbols, providerMap)
        }
        console.warn(`[market_cache] Rate limit hit, waiting 70s... (${rateLimitRetries}/${MAX_RATE_LIMIT_RETRIES + 1})`)
        await new Promise((r) => setTimeout(r, 70000))
        i -= CHUNK
        continue
      }
      rateLimitRetries = 0

      if (!res.ok) {
        console.warn(`[market_cache] Twelve Data quote chunk failed: ${res.status}`, JSON.stringify(data).slice(0, 200))
        continue
      }

      if (data.status === "error" || data.code) {
        console.warn(`[market_cache] Twelve Data error:`, data.message || data.code, data)
        continue
      }

      let list = Array.isArray(data.data) ? data.data : (data.symbol ? [data] : [])
      if (list.length === 0 && data.data && typeof data.data === "object" && !Array.isArray(data.data)) {
        list = Object.entries(data.data).map(([sym, v]) => ({ ...(v || {}), symbol: sym }))
      }
      if (list.length === 0) {
        const skipKeys = new Set(["status", "code", "message", "meta", "data"])
        const topLevel = Object.entries(data || {}).filter(([k]) => !skipKeys.has(k))
        for (const [sym, v] of topLevel) {
          if (v && typeof v === "object" && !Array.isArray(v) && ("close" in v || "price" in v)) {
            list.push({ ...v, symbol: sym })
          }
        }
      }
      if (list.length === 0) {
        console.warn("[market_cache] Chunk empty. Response keys:", Object.keys(data || {}), "sample:", JSON.stringify(data).slice(0, 300))
      }
      const symbolToOurs = Object.fromEntries(chunk.map((s, idx) => [tdSymbols[idx], s]))
      for (let j = 0; j < list.length; j++) {
        const q = list[j]
        const tdSym = q.symbol || ""
        const sym = symbolToOurs[tdSym] || reverseSymbol(tdSym) || chunk[j]
        const close = parseFloat(q.close)
        const changePct = parseFloat(q.percent_change)
        const volRaw = q.volume ?? q.volume_24h ?? q.trading_volume ?? q["volume_24h"]
        const volParsed = volRaw != null ? parseFloat(String(volRaw).replace(/,/g, "")) : null
        const vol = volParsed != null && !Number.isNaN(volParsed) ? volParsed : null
        const low = q.low != null ? parseFloat(q.low) : null
        const high = q.high != null ? parseFloat(q.high) : null

        if (!Number.isNaN(close)) {
          results.push({
            symbol: sym,
            ts_utc: q.datetime || new Date().toISOString(),
            price: close,
            change_pct: Number.isNaN(changePct) ? null : changePct,
            volume: vol,
            day_low: low,
            day_high: high,
            market_cap: null,
            next_earnings_date: null,
          })
        }
      }

      const receivedSyms = new Set(
        list.map((q) => {
          const td = q.symbol || ""
          return symbolToOurs[td] || reverseSymbol(td) || td
        })
      )
      for (const sym of chunk) {
        if (!receivedSyms.has(sym)) {
          const single = await fetchSingleQuote(sym, providerMap)
          if (single) results.push(single)
          await new Promise((r) => setTimeout(r, 3000))
        }
      }
    } catch (err) {
      console.warn(`[market_cache] Batch quote error:`, err.message)
    }

    if (i + CHUNK < symbols.length) {
      await new Promise((r) => setTimeout(r, 15000))
    }
  }

  return results
}

async function fetchSingleOnly(symbols, providerMap) {
  const results = []
  const total = symbols.length
  for (let i = 0; i < total; i++) {
    const sym = symbols[i]
    const q = await fetchSingleQuote(sym, providerMap)
    if (q) results.push(q)
    if ((i + 1) % 10 === 0 || i === total - 1) {
      console.log(`[market_cache] Single-symbol: ${i + 1}/${total} (${results.length} received)`)
    }
    if (i < total - 1) {
      await new Promise((r) => setTimeout(r, SINGLE_DELAY_MS))
    }
  }
  return results
}

async function fetchSingleQuote(symbol, providerMap) {
  const key = getApiKey()
  if (!key) return null
  const tdSymbol = providerMap[symbol] || toProviderSymbol(symbol)
  try {
    const url = `${BASE}/quote?symbol=${encodeURIComponent(tdSymbol)}&apikey=${key}`
    const res = await fetch(url)
    if (!res.ok) return null
    const q = await res.json()
    if (q.status === "error" || !q.close) return null
    const close = parseFloat(q.close)
    if (Number.isNaN(close)) return null
    const volRaw = q.volume ?? q.volume_24h ?? q.trading_volume ?? q["volume_24h"]
    const volParsed = volRaw != null ? parseFloat(String(volRaw).replace(/,/g, "")) : null
    const vol = volParsed != null && !Number.isNaN(volParsed) ? volParsed : null
    return {
      symbol,
      ts_utc: q.datetime || new Date().toISOString(),
      price: close,
      change_pct: parseFloat(q.percent_change) || null,
      volume: vol,
      day_low: q.low != null ? parseFloat(q.low) : null,
      day_high: q.high != null ? parseFloat(q.high) : null,
      market_cap: null,
      next_earnings_date: null,
    }
  } catch {
    return null
  }
}

/**
 * Create WebSocket connection for real-time quotes.
 * Subscribes to symbols, writes updates to db.
 */
export async function createQuoteWebSocket(symbols, onMessage, maxSubs = 200) {
  const key = getApiKey()
  if (!key || symbols.length === 0) return null

  const sub = symbols.slice(0, maxSubs)
  const tdSymbols = sub.map((s) => toProviderSymbol(s))
  const symbolParam = tdSymbols.join(",")
  const url = `${WS_BASE}?symbol=${encodeURIComponent(symbolParam)}&apikey=${key}`

  try {
    const { default: WebSocket } = await import("ws")
    const ws = new WebSocket(url)

    ws.on("message", (data) => {
      try {
        const msg = JSON.parse(data.toString())
        if (msg.event === "price" && msg.symbol) {
          const tdSym = msg.symbol
          const sym = reverseSymbol(tdSym) || tdSym.replace("/", "")
          const price = parseFloat(msg.price)
          const volRaw = msg.volume ?? msg.volume_24h ?? msg.trading_volume ?? msg["volume_24h"]
          const volParsed = volRaw != null ? parseFloat(String(volRaw)) : null
          const vol = volParsed != null && !Number.isNaN(volParsed) ? volParsed : null
          if (!Number.isNaN(price)) {
            onMessage({
              symbol: sym,
              ts_utc: new Date().toISOString(),
              price,
              change_pct: parseFloat(msg.percent_change) || null,
              volume: vol,
              day_low: null,
              day_high: null,
              market_cap: null,
              next_earnings_date: null,
            })
          }
        }
      } catch {
        // ignore parse errors
      }
    })

    ws.on("error", (err) => {
      console.warn("[market_cache] WebSocket error:", err.message)
    })

    ws.on("close", () => {
      console.log("[market_cache] WebSocket closed")
    })

    return ws
  } catch (err) {
    console.warn("[market_cache] WebSocket init failed:", err.message)
    return null
  }
}
