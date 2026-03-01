"use client"

import { useMemo, useState, useEffect } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { assetClassDisplayName } from "@/lib/assetTypes"
import type { ScreenerRow } from "@/lib/screenerTypes"
import { ScreenerTable } from "@/components/symbol/ScreenerTable"

type CoreEarnings = { asset_class: string; assets: ScreenerRow[] }[]

type Props = {
  rows: ScreenerRow[]
  core: CoreEarnings
  earnings: CoreEarnings
  assetClassDisplayName: (ac: string) => string
  loading: boolean
}

export function MarketsContent({
  rows,
  core,
  earnings,
  assetClassDisplayName,
  loading,
}: Props) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const assetClassFromUrl = searchParams.get("asset_class") ?? ""

  const [assetClassFilter, setAssetClassFilter] = useState<string>(assetClassFromUrl)
  const [globalSearch, setGlobalSearch] = useState("")

  useEffect(() => {
    setAssetClassFilter(assetClassFromUrl)
  }, [assetClassFromUrl])

  const updateAssetClass = (value: string) => {
    setAssetClassFilter(value)
    const url = new URL(window.location.href)
    if (value) {
      url.searchParams.set("asset_class", value)
    } else {
      url.searchParams.delete("asset_class")
    }
    router.replace(url.pathname + url.search)
  }

  const filteredRows = useMemo(() => {
    let out = rows
    if (assetClassFilter) {
      out = out.filter((r) => r.asset_class === assetClassFilter)
    }
    const q = globalSearch.trim().toUpperCase()
    if (q) {
      out = out.filter((r) => r.symbol.toUpperCase().includes(q))
    }
    return out
  }, [rows, assetClassFilter, globalSearch])

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-zinc-900">Markets</h1>
        <div className="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search symbol..."
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            className="h-8 w-48 rounded border border-zinc-200 px-2.5 py-1 text-sm focus:border-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-400"
          />
          <select
            value={assetClassFilter}
            onChange={(e) => updateAssetClass(e.target.value)}
            className="h-8 rounded border border-zinc-200 px-2.5 py-1 text-sm"
          >
            <option value="">Any</option>
            {Array.from(new Set(rows.map((r) => r.asset_class))).sort().map((ac) => (
              <option key={ac} value={ac}>
                {assetClassDisplayName(ac)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="mt-1.5 text-xs text-zinc-500">
        Tip: click an asset class, or use filters below to screen.
      </p>

      <div className="mt-3 space-y-2">
        <section>
          <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
            Core Macro
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {core.map(({ asset_class: ac, assets: acList }) => (
              <button
                key={ac}
                type="button"
                onClick={() => updateAssetClass(assetClassFilter === ac ? "" : ac)}
                className={`rounded-full px-2.5 py-1 text-xs transition ${
                  assetClassFilter === ac
                    ? "bg-[#0d4f3c] text-white"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                }`}
              >
                {assetClassDisplayName(ac)} ({acList.length})
              </button>
            ))}
          </div>
        </section>

        <section>
          <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
            Earnings Universe
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {earnings.map(({ asset_class: ac, assets: acList }) => (
              <button
                key={ac}
                type="button"
                onClick={() => updateAssetClass(assetClassFilter === ac ? "" : ac)}
                className={`rounded-full px-2.5 py-1 text-xs transition ${
                  assetClassFilter === ac
                    ? "bg-[#0d4f3c] text-white"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                }`}
              >
                {assetClassDisplayName(ac)} ({acList.length})
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="mt-6">
        {loading ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : (
          <ScreenerTable
            rows={filteredRows}
            assetClassFilter={assetClassFilter}
            onAssetClassFilterChange={updateAssetClass}
            assetClasses={Array.from(new Set(rows.map((r) => r.asset_class))).sort()}
            isPaid={false}
            sortFromUrl={searchParams.get("sort") ?? undefined}
            sortDirFromUrl={searchParams.get("dir") === "desc" ? "desc" : undefined}
          />
        )}
      </div>
    </div>
  )
}
