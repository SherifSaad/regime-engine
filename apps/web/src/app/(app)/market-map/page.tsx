import Link from "next/link"
import { riApi } from "@/lib/api"

const BUCKET_COLORS: Record<string, string> = {
  LOW: "bg-emerald-100 border-emerald-300 text-emerald-800",
  MED: "bg-amber-100 border-amber-300 text-amber-800",
  HIGH: "bg-rose-100 border-rose-300 text-rose-800",
}

export default async function MarketMapPage() {
  let assets: { symbol: string; asset_class: string }[] = []
  try {
    const list = await riApi.assets()
    assets = list.map((a) => ({ symbol: a.symbol, asset_class: a.asset_class }))
  } catch {
    assets = []
  }

  const byClass = assets.reduce<Record<string, typeof assets>>((acc, a) => {
    const ac = a.asset_class || "Other"
    if (!acc[ac]) acc[ac] = []
    acc[ac].push(a)
    return acc
  }, {})

  const classes = Object.keys(byClass).sort()

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Market Map</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Dense scan by escalation bucket and percentile. FX · Indices ·
        Commodities · Crypto · Rates.
      </p>

      {/* Bucket legend */}
      <div className="mt-6 flex flex-wrap gap-4">
        <span className="text-xs font-medium text-zinc-500">Bucket:</span>
        {["LOW", "MED", "HIGH"].map((b) => (
          <span
            key={b}
            className={`rounded border px-2 py-1 text-xs font-medium ${BUCKET_COLORS[b] ?? "bg-zinc-100 border-zinc-300 text-zinc-700"}`}
          >
            {b}
          </span>
        ))}
      </div>

      <div className="mt-8 space-y-6">
        {classes.map((ac) => (
          <div
            key={ac}
            className="rounded-lg border border-zinc-200 bg-white p-6"
          >
            <h2 className="font-medium text-zinc-900">{ac}</h2>
            <div className="mt-4 grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10">
              {byClass[ac].map((a) => (
                <Link
                  key={a.symbol}
                  href={`/markets/${a.symbol}`}
                  className="rounded border border-zinc-200 px-2 py-2 text-center text-sm font-medium text-zinc-700 hover:border-[#0d4f3c] hover:bg-[#0d4f3c]/5 hover:text-[#0d4f3c]"
                >
                  {a.symbol}
                  <span className="mt-1 block text-xs font-normal text-zinc-500">
                    —
                  </span>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      {assets.length === 0 && (
        <div className="mt-8 rounded-lg border border-zinc-200 bg-white p-6">
          <p className="text-sm text-zinc-500">
            No assets. API or registry unavailable. (Placeholder grid—bucket
            and percentile will populate when compute.db data is wired.)
          </p>
        </div>
      )}
    </div>
  )
}
