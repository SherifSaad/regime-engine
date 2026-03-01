import path from "path"
import fs from "fs"
import { riApi } from "./api"
import type { AssetItem } from "./assetTypes"

export type { AssetItem }

const CORE_MACRO_CLASSES = new Set([
  "FX",
  "CRYPTO",
  "Commodities",
  "Fixed Income",
  "US_EQUITY_INDEX",
])
const EARNINGS_CLASSES = new Set(["US_EQUITY"])

export function universeFromAssetClass(ac: string): "core" | "earnings" {
  if (CORE_MACRO_CLASSES.has(ac)) return "core"
  if (EARNINGS_CLASSES.has(ac)) return "earnings"
  return "core"
}

export { assetClassDisplayName } from "./assetTypes"

export async function loadAssets(): Promise<AssetItem[]> {
  try {
    const list = await riApi.assets()
    return list.map((a) => ({
      symbol: a.symbol,
      name: a.name ?? a.symbol,
      asset_class: a.asset_class,
      has_compute: a.has_compute,
    }))
  } catch {
    // Fallback: read universe.json from repo root
    try {
      const root = path.resolve(process.cwd(), "..", "..")
      const universePath = path.join(root, "universe.json")
      const raw = fs.readFileSync(universePath, "utf-8")
      const data = JSON.parse(raw) as { assets?: Array<{ symbol: string; name?: string; asset_class?: string }> }
      const assets = data.assets ?? []
      return assets.map((a) => ({
        symbol: a.symbol,
        name: a.name ?? a.symbol,
        asset_class: a.asset_class ?? "UNKNOWN",
      }))
    } catch {
      return []
    }
  }
}

export function groupByAssetClass(assets: AssetItem[]) {
  const byClass = new Map<string, AssetItem[]>()
  for (const a of assets) {
    const ac = a.asset_class || "Other"
    if (!byClass.has(ac)) byClass.set(ac, [])
    byClass.get(ac)!.push(a)
  }
  for (const arr of byClass.values()) {
    arr.sort((x, y) => x.symbol.localeCompare(y.symbol))
  }
  return byClass
}

export function splitByUniverse(byClass: Map<string, AssetItem[]>) {
  const core: { asset_class: string; assets: AssetItem[] }[] = []
  const earnings: { asset_class: string; assets: AssetItem[] }[] = []
  const order = [
    "FX",
    "US_EQUITY_INDEX",
    "Commodities",
    "CRYPTO",
    "Fixed Income",
    "US_EQUITY",
  ]
  const seen = new Set<string>()
  for (const ac of order) {
    const assets = byClass.get(ac)
    if (!assets?.length || seen.has(ac)) continue
    seen.add(ac)
    const universe = universeFromAssetClass(ac)
    const entry = { asset_class: ac, assets }
    if (universe === "core") core.push(entry)
    else earnings.push(entry)
  }
  for (const [ac, assets] of byClass) {
    if (seen.has(ac)) continue
    const universe = universeFromAssetClass(ac)
    const entry = { asset_class: ac, assets }
    if (universe === "core") core.push(entry)
    else earnings.push(entry)
  }
  return { core, earnings }
}
