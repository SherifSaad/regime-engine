#!/usr/bin/env node
/**
 * Market cache service.
 * A1) Periodic batch refresh (full universe)
 * A2) WebSocket streaming for active symbols (optional)
 */
import path from "path"
import fs from "fs"
import { fileURLToPath } from "url"
import dotenv from "dotenv"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: path.resolve(__dirname, "..", "..", ".env") })
import { getDb, upsertBatch, upsert, updateMarketCapAndEarnings } from "./db.js"
import { fetchBatchQuotes, createQuoteWebSocket } from "./twelvedata.js"
import { fetchStatistics, fetchEarningsNextDate } from "./equityEnrichment.js"

const PROJECT_ROOT = path.resolve(__dirname, "..", "..")
const DATA_DIR = path.join(PROJECT_ROOT, "data")
const ACTIVE_SYMBOLS_PATH = path.join(DATA_DIR, "market_active_symbols.json")
const UNIVERSE_PATHS = [
  path.join(PROJECT_ROOT, "apps", "web", "public", "universe.json"),
  path.join(PROJECT_ROOT, "universe.json"),
]

const REFRESH_MINUTES = parseInt(process.env.MARKET_CACHE_REFRESH_MINUTES || "10", 10)
const STREAM_MAX_SUBS = parseInt(process.env.MARKET_STREAM_MAX_SUBS || "200", 10)

const EQUITY_CLASSES = new Set(["US_EQUITY", "US_EQUITY_INDEX"])

function loadUniverse() {
  for (const p of UNIVERSE_PATHS) {
    try {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, "utf-8")
        const data = JSON.parse(raw)
        const assets = data.assets || []
        const symbols = assets.map((a) => a.symbol)
        const providerMap = Object.fromEntries(
          assets.filter((a) => a.provider_symbol).map((a) => [a.symbol, a.provider_symbol])
        )
        const equitySymbols = assets
          .filter((a) => EQUITY_CLASSES.has(a.asset_class))
          .map((a) => a.symbol)
        return { symbols, providerMap, equitySymbols }
      }
    } catch {
      continue
    }
  }
  return { symbols: [], providerMap: {}, equitySymbols: [] }
}

function loadActiveSymbols() {
  try {
    if (fs.existsSync(ACTIVE_SYMBOLS_PATH)) {
      const raw = fs.readFileSync(ACTIVE_SYMBOLS_PATH, "utf-8")
      const data = JSON.parse(raw)
      return Array.isArray(data.symbols) ? data.symbols : []
    }
  } catch {
    // ignore
  }
  return []
}

async function runEquityEnrichment() {
  const { equitySymbols, providerMap } = loadUniverse()
  if (equitySymbols.length === 0) return
  console.log(`[market_cache] Equity enrichment: ${equitySymbols.length} symbols`)
  let updated = 0
  for (let i = 0; i < equitySymbols.length; i++) {
    const sym = equitySymbols[i]
    try {
      const [marketCap, nextEarnings] = await Promise.all([
        fetchStatistics(sym, providerMap),
        fetchEarningsNextDate(sym, providerMap),
      ])
      if (marketCap != null || nextEarnings != null) {
        updateMarketCapAndEarnings(sym, marketCap, nextEarnings)
        updated++
      }
    } catch {
      // skip
    }
    if ((i + 1) % 10 === 0) {
      await new Promise((r) => setTimeout(r, 2000))
    }
  }
  console.log(`[market_cache] Equity enrichment: updated ${updated} rows`)
}

async function runBatchRefresh() {
  const { symbols, providerMap } = loadUniverse()
  if (symbols.length === 0) {
    console.log("[market_cache] No universe found, skipping batch refresh")
    return
  }

  const limit = parseInt(process.env.MARKET_CACHE_LIMIT || "0", 10)
  const toFetch = limit > 0 ? symbols.slice(0, limit) : symbols
  if (limit > 0) {
    console.log(`[market_cache] Batch refresh: ${toFetch.length} symbols (limited by MARKET_CACHE_LIMIT=${limit})`)
  } else {
    console.log(`[market_cache] Batch refresh: ${toFetch.length} symbols`)
  }
  if (!process.env.TWELVEDATA_API_KEY?.trim()) {
    console.warn("[market_cache] TWELVEDATA_API_KEY not set. Set it in .env at project root.")
    return
  }
  const rows = await fetchBatchQuotes(toFetch, providerMap)
  if (rows.length > 0) {
    upsertBatch(rows)
    console.log(`[market_cache] Wrote ${rows.length} rows to market_latest`)
  } else {
    console.warn("[market_cache] No quotes received from Twelve Data. Check TWELVEDATA_API_KEY and rate limits.")
  }
}

async function runStreamLoop() {
  const active = loadActiveSymbols()
  if (active.length === 0) return null

  const subs = active.slice(0, STREAM_MAX_SUBS)
  console.log(`[market_cache] WebSocket subscribing to ${subs.length} active symbols`)

  const ws = await createQuoteWebSocket(
    subs,
    (row) => {
      upsert(row)
    },
    STREAM_MAX_SUBS
  )
  return ws
}

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true })
  }
}

const ENRICHMENT_HOURS = parseInt(process.env.MARKET_ENRICHMENT_HOURS || "24", 10)

async function main() {
  ensureDataDir()
  getDb()

  await runBatchRefresh()
  await runEquityEnrichment()

  let ws = await runStreamLoop()
  const streamInterval = setInterval(loadActiveSymbols, 30_000)

  const batchInterval = setInterval(async () => {
    await runBatchRefresh()
  }, REFRESH_MINUTES * 60 * 1000)

  const enrichmentInterval = setInterval(async () => {
    await runEquityEnrichment()
  }, ENRICHMENT_HOURS * 60 * 60 * 1000)

  const reconnectInterval = setInterval(async () => {
    const active = loadActiveSymbols()
    if (active.length > 0 && (!ws || ws.readyState !== 1)) {
      if (ws) {
        try {
          ws.close()
        } catch {}
      }
      ws = await runStreamLoop()
    }
  }, 60_000)

  process.on("SIGINT", () => {
    clearInterval(batchInterval)
    clearInterval(enrichmentInterval)
    clearInterval(streamInterval)
    clearInterval(reconnectInterval)
    if (ws) {
      try {
        ws.close()
      } catch {}
    }
    process.exit(0)
  })
}

main().catch((err) => {
  console.error("[market_cache] Fatal:", err)
  process.exit(1)
})
