/**
 * Read from market_latest SQLite (shared with market_cache service).
 * Used by marketSnapshot and screener.
 */
import Database from "better-sqlite3"
import path from "path"
import fs from "fs"

const PROJECT_ROOT = path.resolve(process.cwd(), "..", "..")
const DB_PATH = path.join(PROJECT_ROOT, "data", "market_latest.db")

let db: Database.Database | null = null

function getDb(): Database.Database | null {
  if (!fs.existsSync(DB_PATH)) return null
  if (db) return db
  try {
    db = new Database(DB_PATH, { readonly: true })
    return db
  } catch {
    return null
  }
}

export type MarketLatestRow = {
  symbol: string
  ts_utc: string | null
  price: number | null
  change_pct: number | null
  volume: number | null
  day_low: number | null
  day_high: number | null
  market_cap: number | null
  next_earnings_date: string | null
}

export function getMarketLatestAll(): MarketLatestRow[] {
  const d = getDb()
  if (!d) return []
  try {
    return d.prepare("SELECT * FROM market_latest").all() as MarketLatestRow[]
  } catch {
    return []
  }
}

export function getMarketLatestMap(): Record<string, MarketLatestRow> {
  const rows = getMarketLatestAll()
  return Object.fromEntries(rows.map((r) => [r.symbol, r]))
}

export function getMarketLatestBySymbol(symbol: string): MarketLatestRow | null {
  const d = getDb()
  if (!d) return null
  try {
    return d.prepare("SELECT * FROM market_latest WHERE symbol = ?").get(symbol) as MarketLatestRow | null
  } catch {
    return null
  }
}
