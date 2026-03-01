import type { AssetItem } from "./assetTypes"
import type { ScreenerRow } from "./screenerTypes"

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

export function groupByAssetClassScreener(rows: ScreenerRow[]) {
  const byClass = new Map<string, ScreenerRow[]>()
  for (const r of rows) {
    const ac = r.asset_class || "Other"
    if (!byClass.has(ac)) byClass.set(ac, [])
    byClass.get(ac)!.push(r)
  }
  for (const arr of byClass.values()) {
    arr.sort((x, y) => x.symbol.localeCompare(y.symbol))
  }
  return byClass
}

export function splitByUniverseScreener(byClass: Map<string, ScreenerRow[]>) {
  const core: { asset_class: string; assets: ScreenerRow[] }[] = []
  const earnings: { asset_class: string; assets: ScreenerRow[] }[] = []
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
