/**
 * POST /api/market-subscription
 * Body: { symbols: string[] }
 * Writes active symbols to data/market_active_symbols.json for market_cache service.
 */
import { NextResponse } from "next/server"
import path from "path"
import fs from "fs"

const PROJECT_ROOT = path.resolve(process.cwd(), "..", "..")
const DATA_DIR = path.join(PROJECT_ROOT, "data")
const ACTIVE_PATH = path.join(DATA_DIR, "market_active_symbols.json")

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const symbols = Array.isArray(body.symbols) ? body.symbols : []
    const unique = [...new Set(symbols)].slice(0, 200)

    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true })
    }

    fs.writeFileSync(
      ACTIVE_PATH,
      JSON.stringify({
        symbols: unique,
        updated_at: new Date().toISOString(),
      }),
      "utf-8"
    )

    return NextResponse.json({ ok: true, count: unique.length })
  } catch {
    return NextResponse.json({ ok: false }, { status: 500 })
  }
}
