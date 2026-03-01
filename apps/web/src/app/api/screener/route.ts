import path from "path"
import fs from "fs"
import { NextResponse } from "next/server"
import { loadAssets } from "@/lib/loadAssets"
import { getMarketRealtimeLatest } from "@/lib/marketSnapshot"
import type { ScreenerRow } from "@/lib/screenerTypes"

function loadAssetsFallback(): { symbol: string; asset_class: string }[] {
  const candidates = [
    path.join(process.cwd(), "public", "universe.json"),
    path.resolve(process.cwd(), "..", "..", "universe.json"),
    path.resolve(process.cwd(), "..", "universe.json"),
  ]
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, "utf-8")
        const data = JSON.parse(raw) as { assets?: Array<{ symbol: string; asset_class?: string }> }
        const list = data.assets ?? []
        return list.map((a) => ({
          symbol: a.symbol,
          asset_class: a.asset_class ?? "UNKNOWN",
        }))
      }
    } catch {
      continue
    }
  }
  return []
}

export async function GET() {
  try {
    let assets = await loadAssets()
    if (assets.length === 0) {
      assets = loadAssetsFallback().map((a) => ({
        symbol: a.symbol,
        name: a.symbol,
        asset_class: a.asset_class,
      }))
    }
    const snapshot = getMarketRealtimeLatest()

    const rows: ScreenerRow[] = assets.map((a) => {
      const rt = snapshot[a.symbol]
      return {
        symbol: a.symbol,
        asset_class: a.asset_class,
        price: rt?.price ?? null,
        change_pct: rt?.change_pct ?? null,
        volume: rt?.volume ?? null,
        market_cap: rt?.market_cap ?? null,
        next_earnings_date: rt?.next_earnings_date ?? null,
        regime_state: null,
        escalation_pct: null,
        trend_strength: null,
      }
    })

    return NextResponse.json(rows)
  } catch {
    const fallback = loadAssetsFallback()
    const rows: ScreenerRow[] = fallback.map((a) => ({
      symbol: a.symbol,
      asset_class: a.asset_class,
      price: null,
      change_pct: null,
      volume: null,
      market_cap: null,
      next_earnings_date: null,
      regime_state: null,
      escalation_pct: null,
      trend_strength: null,
    }))
    return NextResponse.json(rows)
  }
}
