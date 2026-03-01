"use client"

import Link from "next/link"
import { useMemo, useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { assetClassDisplayName } from "@/lib/assetTypes"
import type { ScreenerRow } from "@/lib/screenerTypes"

const PAGE_SIZES = [25, 50, 100, 200]
const REGIME_OPTIONS = ["TRENDING_BULL", "TRENDING_BEAR", "CHOP_RISK", "SHOCK", "PANIC_RISK", "TRANSITION"]

type SortKey = "symbol" | "price" | "change_pct" | "volume" | "market_cap" | "next_earnings_date" | "escalation_pct" | "trend_strength"
const DEFAULT_SORT: SortKey = "symbol"
const SORT_KEYS: SortKey[] = ["symbol", "price", "change_pct", "volume", "market_cap", "next_earnings_date", "escalation_pct", "trend_strength"]

type Props = {
  rows: ScreenerRow[]
  assetClassFilter?: string
  onAssetClassFilterChange?: (value: string) => void
  assetClasses?: string[]
  isPaid?: boolean
  sortFromUrl?: string
  sortDirFromUrl?: "asc" | "desc"
}

export function ScreenerTable({
  rows,
  assetClassFilter = "",
  onAssetClassFilterChange,
  assetClasses: assetClassesProp,
  isPaid = false,
  sortFromUrl,
  sortDirFromUrl,
}: Props) {
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [showFilters, setShowFilters] = useState(true)
  const [priceMin, setPriceMin] = useState("")
  const [priceMax, setPriceMax] = useState("")
  const [volumeMin, setVolumeMin] = useState("")
  const [marketCapMin, setMarketCapMin] = useState("")
  const [marketCapMax, setMarketCapMax] = useState("")
  const [earningsWindow, setEarningsWindow] = useState<number>(0)
  const [regimeState, setRegimeState] = useState("")
  const [escalationMin, setEscalationMin] = useState("")
  const [trendStrengthMin, setTrendStrengthMin] = useState("")
  const router = useRouter()
  const [sortKey, setSortKey] = useState<SortKey>(
    sortFromUrl && SORT_KEYS.includes(sortFromUrl as SortKey) ? (sortFromUrl as SortKey) : DEFAULT_SORT
  )
  const [sortDir, setSortDir] = useState<"asc" | "desc">(sortDirFromUrl ?? "asc")

  useEffect(() => {
    if (sortFromUrl && SORT_KEYS.includes(sortFromUrl as SortKey)) {
      setSortKey(sortFromUrl as SortKey)
      setSortDir(sortDirFromUrl === "desc" ? "desc" : "asc")
    } else {
      setSortKey(DEFAULT_SORT)
      setSortDir("asc")
    }
  }, [sortFromUrl, sortDirFromUrl])

  const assetClasses = useMemo(
    () => assetClassesProp ?? Array.from(new Set(rows.map((r) => r.asset_class))).sort(),
    [assetClassesProp, rows]
  )

  const clearFilters = () => {
    setPriceMin("")
    setPriceMax("")
    setVolumeMin("")
    setMarketCapMin("")
    setMarketCapMax("")
    setEarningsWindow(0)
    setRegimeState("")
    setEscalationMin("")
    setTrendStrengthMin("")
    onAssetClassFilterChange?.("")
    setPage(0)
  }

  const filtered = useMemo(() => {
    let out = rows
    if (assetClassFilter && assetClassFilter.trim() !== "") {
      out = out.filter((r) => r.asset_class === assetClassFilter)
    }
    const pMin = parseFloat(priceMin)
    if (!Number.isNaN(pMin)) {
      out = out.filter((r) => r.price != null && r.price >= pMin)
    }
    const pMax = parseFloat(priceMax)
    if (!Number.isNaN(pMax)) {
      out = out.filter((r) => r.price != null && r.price <= pMax)
    }
    const vMin = parseFloat(volumeMin)
    if (!Number.isNaN(vMin) && vMin > 0) {
      out = out.filter((r) => r.volume != null && r.volume >= vMin)
    }
    const mcMin = parseFloat(marketCapMin)
    if (!Number.isNaN(mcMin) && mcMin > 0) {
      out = out.filter((r) => r.market_cap != null && r.market_cap >= mcMin)
    }
    const mcMax = parseFloat(marketCapMax)
    if (!Number.isNaN(mcMax) && mcMax > 0) {
      out = out.filter((r) => r.market_cap != null && r.market_cap <= mcMax)
    }
    if (earningsWindow > 0) {
      const now = new Date()
      now.setHours(0, 0, 0, 0)
      const end = new Date(now)
      end.setDate(end.getDate() + earningsWindow)
      out = out.filter((r) => {
        if (!r.next_earnings_date) return false
        const d = new Date(r.next_earnings_date)
        d.setHours(0, 0, 0, 0)
        return d >= now && d <= end
      })
    }
    if (regimeState && regimeState.trim() !== "") {
      out = out.filter((r) => r.regime_state === regimeState)
    }
    const escMin = parseFloat(escalationMin)
    if (!Number.isNaN(escMin) && escMin > 0) {
      out = out.filter((r) => r.escalation_pct != null && r.escalation_pct >= escMin)
    }
    const tsMin = parseFloat(trendStrengthMin)
    if (!Number.isNaN(tsMin) && tsMin > 0) {
      out = out.filter((r) => r.trend_strength != null && r.trend_strength >= tsMin)
    }
    return out
  }, [
    rows,
    assetClassFilter,
    priceMin,
    priceMax,
    volumeMin,
    marketCapMin,
    marketCapMax,
    earningsWindow,
    regimeState,
    escalationMin,
    trendStrengthMin,
  ])

  const sorted = useMemo(() => {
    const arr = [...filtered]
    const cmp = (a: ScreenerRow, b: ScreenerRow) => {
      const av = a[sortKey as keyof ScreenerRow]
      const bv = b[sortKey as keyof ScreenerRow]
      const aNull = av == null || av === ""
      const bNull = bv == null || bv === ""
      if (aNull && bNull) return 0
      if (aNull) return 1
      if (bNull) return -1
      if (sortKey === "symbol" || sortKey === "next_earnings_date") {
        const sa = String(av)
        const sb = String(bv)
        return sortDir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa)
      }
      const na = typeof av === "number" ? av : parseFloat(String(av))
      const nb = typeof bv === "number" ? bv : parseFloat(String(bv))
      if (Number.isNaN(na) && Number.isNaN(nb)) return 0
      if (Number.isNaN(na)) return 1
      if (Number.isNaN(nb)) return -1
      return sortDir === "asc" ? na - nb : nb - na
    }
    arr.sort(cmp)
    return arr
  }, [filtered, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    let newKey = sortKey
    let newDir = sortDir
    if (key === sortKey) {
      if (sortDir === "asc") {
        newDir = "desc"
      } else {
        newKey = DEFAULT_SORT
        newDir = "asc"
      }
    } else {
      newKey = key
      newDir = "asc"
    }
    setSortKey(newKey)
    setSortDir(newDir)
    setPage(0)
    const url = new URL(window.location.href)
    if (newKey === DEFAULT_SORT && newDir === "asc") {
      url.searchParams.delete("sort")
      url.searchParams.delete("dir")
    } else {
      url.searchParams.set("sort", newKey)
      url.searchParams.set("dir", newDir)
    }
    router.replace(url.pathname + url.search)
  }

  const totalPages = Math.ceil(sorted.length / pageSize) || 1
  const start = page * pageSize
  const pageData = sorted.slice(start, start + pageSize)

  const visibleSymbols = useMemo(
    () => pageData.map((r) => r.symbol),
    [page, pageSize, sorted]
  )
  useEffect(() => {
    if (visibleSymbols.length === 0) return
    fetch("/api/market-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: visibleSymbols }),
    }).catch(() => {})
  }, [visibleSymbols.join(",")])

  const hasMarketData = useMemo(
    () => rows.length > 0 && rows.some((r) => r.price != null || r.volume != null || r.market_cap != null),
    [rows]
  )

  const formatVal = (v: number | null, fmt: "price" | "pct" | "vol" | "cap") => {
    if (v == null) return "—"
    if (fmt === "price") return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    if (fmt === "pct") return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`
    if (fmt === "vol") return v >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v.toLocaleString()
    if (fmt === "cap") return v >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v.toLocaleString()
    return "—"
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-zinc-200 bg-white">
        <div className="flex items-center justify-between border-b border-zinc-100 px-3 py-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowFilters((s) => !s)}
              className="text-sm font-medium text-zinc-900"
            >
              Filters {showFilters ? "−" : "+"}
            </button>
            {!hasMarketData && rows.length > 0 && (
              <span className="text-[11px] text-zinc-400">
                Market fields not loaded yet (coming from snapshot).
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={clearFilters}
              className="rounded border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-50"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => setPage(0)}
              className="rounded bg-zinc-200 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-300"
            >
              Apply
            </button>
          </div>
        </div>
        {showFilters && (
          <>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-3 py-2 sm:grid-cols-4 md:grid-cols-6">
              <div>
                <label className="block text-xs text-zinc-500">Asset Class</label>
                <select
                  value={assetClassFilter}
                  onChange={(e) => { onAssetClassFilterChange?.(e.target.value); setPage(0) }}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs"
                >
                  <option value="">Any</option>
                  {assetClasses.map((ac) => (
                    <option key={ac} value={ac}>
                      {assetClassDisplayName(ac)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Price Min</label>
                <input
                  type="number"
                  value={priceMin}
                  onChange={(e) => { setPriceMin(e.target.value); setPage(0) }}
                  placeholder="Min"
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Price Max</label>
                <input
                  type="number"
                  value={priceMax}
                  onChange={(e) => { setPriceMax(e.target.value); setPage(0) }}
                  placeholder="Max"
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Volume Min</label>
                <input
                  type="number"
                  value={volumeMin}
                  onChange={(e) => { setVolumeMin(e.target.value); setPage(0) }}
                  placeholder="Min"
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Market Cap Min <span className="text-zinc-400">(USD)</span></label>
                <input
                  type="number"
                  value={marketCapMin}
                  onChange={(e) => { setMarketCapMin(e.target.value); setPage(0) }}
                  placeholder="e.g. 10M"
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Market Cap Max <span className="text-zinc-400">(USD)</span></label>
                <input
                  type="number"
                  value={marketCapMax}
                  onChange={(e) => { setMarketCapMax(e.target.value); setPage(0) }}
                  placeholder="e.g. 10M"
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Earnings Window</label>
                <div className="mt-0.5 flex gap-1">
                  {([0, 7, 14, 30] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => { setEarningsWindow(d); setPage(0) }}
                      className={`rounded px-2 py-1 text-xs ${
                        earningsWindow === d
                          ? "bg-[#0d4f3c] text-white"
                          : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                      }`}
                    >
                      {d === 0 ? "Any" : `${d}d`}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Regime State</label>
                <select
                  value={regimeState}
                  onChange={(e) => { setRegimeState(e.target.value); setPage(0) }}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs"
                >
                  <option value="">Any</option>
                  {REGIME_OPTIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Escalation % &gt;</label>
                <input
                  type="number"
                  value={escalationMin}
                  onChange={(e) => { setEscalationMin(e.target.value); setPage(0) }}
                  placeholder="Min"
                  min={0}
                  max={100}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-500">Trend Strength &gt;</label>
                <input
                  type="number"
                  value={trendStrengthMin}
                  onChange={(e) => { setTrendStrengthMin(e.target.value); setPage(0) }}
                  placeholder="Min"
                  min={0}
                  max={100}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-xs tabular-nums"
                />
              </div>
            </div>
            <div className="border-t border-zinc-100 px-3 py-1.5">
              <span className="text-xs text-zinc-500">{sorted.length} symbols</span>
            </div>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div />
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span>Show</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(0)
            }}
            className="rounded border border-zinc-200 px-1.5 py-0.5 text-xs"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <span className="tabular-nums">
            {sorted.length === 0 ? "0" : `${start + 1}–${Math.min(start + pageSize, sorted.length)}`} of {sorted.length}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="table-fixed w-full min-w-[900px] text-xs">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="w-[100px] px-2 py-1.5 text-left font-medium text-zinc-700 whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("symbol")}>
                Symbol {sortKey === "symbol" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[90px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("price")}>
                Price {sortKey === "price" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[90px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("change_pct")}>
                Change % {sortKey === "change_pct" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[100px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("volume")}>
                Volume {sortKey === "volume" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[110px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("market_cap")}>
                Market Cap {sortKey === "market_cap" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[110px] px-2 py-1.5 text-left font-medium text-zinc-700 whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("next_earnings_date")}>
                Next Earnings {sortKey === "next_earnings_date" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[120px] px-2 py-1.5 text-center font-medium text-zinc-700 whitespace-nowrap">Regime State</th>
              <th className="w-[70px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("escalation_pct")}>
                Esc % {sortKey === "escalation_pct" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="w-[80px] px-2 py-1.5 text-right font-medium text-zinc-700 tabular-nums whitespace-nowrap cursor-pointer hover:bg-zinc-100" onClick={() => handleSort("trend_strength")}>
                Trend Str {sortKey === "trend_strength" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
            </tr>
          </thead>
          <tbody>
            {pageData.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-sm text-zinc-500">
                  No matches. Clear filters.
                </td>
              </tr>
            ) : (
              pageData.map((r, i) => (
                <tr
                  key={r.symbol}
                  className={`border-b border-zinc-100 last:border-0 hover:bg-zinc-50 ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                >
                  <td className="w-[100px] px-2 py-1.5 font-medium whitespace-nowrap">
                    <Link href={`/markets/${r.symbol}`} className="text-[#0d4f3c] hover:underline">
                      {r.symbol}
                    </Link>
                  </td>
                  <td className="w-[90px] px-2 py-1.5 text-right tabular-nums text-zinc-700 whitespace-nowrap">{formatVal(r.price, "price")}</td>
                  <td className="w-[90px] px-2 py-1.5 text-right tabular-nums text-zinc-700 whitespace-nowrap">{formatVal(r.change_pct, "pct")}</td>
                  <td className="w-[100px] px-2 py-1.5 text-right tabular-nums text-zinc-600 whitespace-nowrap">{formatVal(r.volume, "vol")}</td>
                  <td className="w-[110px] px-2 py-1.5 text-right tabular-nums text-zinc-600 whitespace-nowrap">
                    {r.market_cap != null ? formatVal(r.market_cap, "cap") : "—"}
                  </td>
                  <td className="w-[110px] px-2 py-1.5 text-left text-zinc-600 whitespace-nowrap">{r.next_earnings_date ?? "—"}</td>
                  <td className={`w-[120px] px-2 py-1.5 text-center whitespace-nowrap ${!isPaid && r.regime_state ? "select-none blur-[2px]" : ""}`}>
                    {r.regime_state ?? "—"}
                  </td>
                  <td className={`w-[70px] px-2 py-1.5 text-right tabular-nums whitespace-nowrap ${!isPaid && r.escalation_pct != null ? "select-none blur-[2px]" : ""}`}>
                    {r.escalation_pct != null ? `${r.escalation_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td className={`w-[80px] px-2 py-1.5 text-right tabular-nums whitespace-nowrap ${!isPaid && r.trend_strength != null ? "select-none blur-[2px]" : ""}`}>
                    {r.trend_strength != null ? `${r.trend_strength.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && filtered.length > 0 && (
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded border border-zinc-200 px-2 py-1 text-xs disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-zinc-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="rounded border border-zinc-200 px-2 py-1 text-xs disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
