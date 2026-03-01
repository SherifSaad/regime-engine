/**
 * SQLite storage for market_latest.
 * Shared by market_cache service and Next.js (via marketCacheDb.ts).
 */
import Database from "better-sqlite3"
import path from "path"
import fs from "fs"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(__dirname, "..", "..")
const DATA_DIR = path.join(PROJECT_ROOT, "data")
const DB_PATH = path.join(DATA_DIR, "market_latest.db")

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

let db = null

export function getDb() {
  if (db) return db
  ensureDir(DATA_DIR)
  db = new Database(DB_PATH)
  db.exec(`
    CREATE TABLE IF NOT EXISTS market_latest (
      symbol TEXT PRIMARY KEY,
      ts_utc TEXT,
      price REAL,
      change_pct REAL,
      volume REAL,
      day_low REAL,
      day_high REAL,
      market_cap REAL,
      next_earnings_date TEXT
    )
  `)
  return db
}

export function upsert(row) {
  const d = getDb()
  d.prepare(`
    INSERT INTO market_latest (symbol, ts_utc, price, change_pct, volume, day_low, day_high, market_cap, next_earnings_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
      ts_utc = excluded.ts_utc,
      price = excluded.price,
      change_pct = excluded.change_pct,
      volume = excluded.volume,
      day_low = excluded.day_low,
      day_high = excluded.day_high,
      market_cap = excluded.market_cap,
      next_earnings_date = excluded.next_earnings_date
  `).run(
    row.symbol,
    row.ts_utc ?? null,
    row.price ?? null,
    row.change_pct ?? null,
    row.volume ?? null,
    row.day_low ?? null,
    row.day_high ?? null,
    row.market_cap ?? null,
    row.next_earnings_date ?? null
  )
}

export function upsertBatch(rows) {
  const d = getDb()
  const stmt = d.prepare(`
    INSERT INTO market_latest (symbol, ts_utc, price, change_pct, volume, day_low, day_high, market_cap, next_earnings_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
      ts_utc = excluded.ts_utc,
      price = excluded.price,
      change_pct = excluded.change_pct,
      volume = excluded.volume,
      day_low = excluded.day_low,
      day_high = excluded.day_high,
      market_cap = excluded.market_cap,
      next_earnings_date = excluded.next_earnings_date
  `)
  const tx = d.transaction((items) => {
    for (const row of items) {
      stmt.run(
        row.symbol,
        row.ts_utc ?? null,
        row.price ?? null,
        row.change_pct ?? null,
        row.volume ?? null,
        row.day_low ?? null,
        row.day_high ?? null,
        row.market_cap ?? null,
        row.next_earnings_date ?? null
      )
    }
  })
  tx(rows)
}

export function getAll() {
  const d = getDb()
  return d.prepare("SELECT * FROM market_latest").all()
}

export function getBySymbol(symbol) {
  const d = getDb()
  return d.prepare("SELECT * FROM market_latest WHERE symbol = ?").get(symbol)
}

export function updateMarketCapAndEarnings(symbol, marketCap, nextEarningsDate) {
  const d = getDb()
  d.prepare(`
    UPDATE market_latest SET market_cap = ?, next_earnings_date = ?
    WHERE symbol = ?
  `).run(marketCap ?? null, nextEarningsDate ?? null, symbol)
}

export function getDbPath() {
  return DB_PATH
}
