"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { assetClassDisplayName, type AssetItem } from "@/lib/assetTypes"

const PAGE_SIZES = [25, 50, 100, 200]

export function SymbolTable({ assets }: { assets: AssetItem[] }) {
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<"symbol" | "asset_class">("symbol")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase()
    if (!q) return assets
    return assets.filter(
      (a) =>
        a.symbol.toUpperCase().includes(q) ||
        (a.name && a.name.toUpperCase().includes(q))
    )
  }, [assets, search])

  const sorted = useMemo(() => {
    const out = [...filtered]
    out.sort((a, b) => {
      const va = a[sortKey]
      const vb = b[sortKey]
      const cmp = va.localeCompare(vb, undefined, { sensitivity: "base" })
      return sortDir === "asc" ? cmp : -cmp
    })
    return out
  }, [filtered, sortKey, sortDir])

  const totalPages = Math.ceil(sorted.length / pageSize) || 1
  const start = page * pageSize
  const pageData = sorted.slice(start, start + pageSize)

  const sort = (key: "symbol" | "asset_class") => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    else setSortKey(key)
    setPage(0)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <input
          type="search"
          placeholder="Search symbol..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(0)
          }}
          className="w-48 rounded border border-zinc-200 px-3 py-1.5 text-sm focus:border-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-400"
        />
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <span>Show</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(0)
            }}
            className="rounded border border-zinc-200 px-2 py-1 text-sm"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <span>
            {start + 1}–{Math.min(start + pageSize, sorted.length)} of{" "}
            {sorted.length}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                <button
                  type="button"
                  onClick={() => sort("symbol")}
                  className="flex items-center gap-1 hover:text-zinc-900"
                >
                  Symbol
                  {sortKey === "symbol" && (
                    <span className="text-zinc-400">{sortDir === "asc" ? "↑" : "↓"}</span>
                  )}
                </button>
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                <button
                  type="button"
                  onClick={() => sort("asset_class")}
                  className="flex items-center gap-1 hover:text-zinc-900"
                >
                  Class
                  {sortKey === "asset_class" && (
                    <span className="text-zinc-400">{sortDir === "asc" ? "↑" : "↓"}</span>
                  )}
                </button>
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                Regime
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                Esc
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                Pctl
              </th>
              <th className="px-4 py-2.5 text-left font-medium text-zinc-700">
                Conf
              </th>
              <th className="px-4 py-2.5 text-right font-medium text-zinc-700">
                —
              </th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((a) => (
              <tr
                key={a.symbol}
                className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50"
              >
                <td className="px-4 py-2 font-medium text-zinc-900">
                  {a.symbol}
                </td>
                <td className="px-4 py-2 text-zinc-600">
                  {assetClassDisplayName(a.asset_class)}
                </td>
                <td className="px-4 py-2 text-zinc-500">—</td>
                <td className="px-4 py-2 text-zinc-500">—</td>
                <td className="px-4 py-2 text-zinc-500">—</td>
                <td className="px-4 py-2 text-zinc-500">—</td>
                <td className="px-4 py-2 text-right">
                  <Link
                    href={`/markets/${a.symbol}`}
                    className="text-[#0d4f3c] hover:underline"
                  >
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded border border-zinc-200 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-zinc-500">
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="rounded border border-zinc-200 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
