"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import { groupByAssetClassScreener, splitByUniverseScreener } from "@/lib/assetGrouping"
import { assetClassDisplayName } from "@/lib/assetTypes"
import type { ScreenerRow } from "@/lib/screenerTypes"
import { MarketsContent } from "./MarketsContent"

export default function MarketsPage() {
  const [rows, setRows] = useState<ScreenerRow[]>([])
  const [loading, setLoading] = useState(true)

  const fetchRows = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch("/api/screener")
      const data = await res.json()
      setRows(Array.isArray(data) ? data : [])
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRows()
  }, [fetchRows])

  const byClass = groupByAssetClassScreener(rows)
  const { core, earnings } = splitByUniverseScreener(byClass)

  return (
    <Suspense fallback={<p className="text-sm text-zinc-500">Loading...</p>}>
      <MarketsContent
        rows={rows}
        core={core}
        earnings={earnings}
        assetClassDisplayName={assetClassDisplayName}
        loading={loading}
      />
    </Suspense>
  )
}
