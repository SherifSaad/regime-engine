import Link from "next/link"
import { riApi } from "@/lib/api"

const FALLBACK_CLASSES = ["FX", "Indices", "Commodities", "Crypto", "Rates"]

export default async function GlobalOverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ asset_class?: string }>
}) {
  const { asset_class } = await searchParams
  let stats = null
  let classes: string[] = FALLBACK_CLASSES
  let assets: { symbol: string; name: string }[] = []
  try {
    stats = await riApi.stats()
    classes = stats?.asset_classes?.length
      ? stats.asset_classes
      : FALLBACK_CLASSES
    if (asset_class) {
      const list = await riApi.assets(asset_class)
      assets = list.map((a) => ({ symbol: a.symbol, name: a.name }))
    }
  } catch {
    // API may be unavailable
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">
        Global Overview
      </h1>
      <p className="mt-1 text-sm text-zinc-500">
        Cross-asset snapshot. Filter by asset class to drill into symbols.
      </p>

      {/* Filter by asset class */}
      <div className="mt-6 flex flex-wrap gap-2">
        <Link
          href="/overview"
          className={`rounded border px-4 py-2 text-sm font-medium ${
            !asset_class
              ? "border-[#0d4f3c] bg-[#0d4f3c]/10 text-[#0d4f3c]"
              : "border-zinc-200 text-zinc-700 hover:bg-zinc-50"
          }`}
        >
          All
        </Link>
        {classes.map((ac) => (
          <Link
            key={ac}
            href={`/overview?asset_class=${encodeURIComponent(ac)}`}
            className={`rounded border px-4 py-2 text-sm font-medium ${
              asset_class === ac
                ? "border-[#0d4f3c] bg-[#0d4f3c]/10 text-[#0d4f3c]"
                : "border-zinc-200 text-zinc-700 hover:bg-zinc-50"
            }`}
          >
            {ac}
          </Link>
        ))}
      </div>

      <div className="mt-8 grid gap-6">
        {/* Composite / cross-asset snapshot */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-medium text-zinc-900">
            Cross-Asset Snapshot
          </h2>
          <p className="mt-2 text-sm text-zinc-500">
            Regime distribution, escalation bucket mix, consensus
            alignment. (Data placeholder—wired when manifest/API ready.)
          </p>
        </div>

        {/* Stats when available */}
        {stats && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <h2 className="font-medium text-zinc-900">Stats</h2>
            <p className="mt-2 text-sm text-zinc-500">
              {stats.assets_total} assets · {stats.assets_with_compute ?? stats.assets_total} with
              compute · {stats.asset_classes?.join(", ") ?? "—"}
            </p>
          </div>
        )}

        {/* Filtered asset list */}
        {asset_class && assets.length > 0 && (
          <div className="rounded-lg border border-zinc-200 bg-white p-6">
            <h2 className="font-medium text-zinc-900">
              {asset_class} symbols
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {assets.map((a) => (
                <Link
                  key={a.symbol}
                  href={`/markets/${a.symbol}`}
                  className="rounded border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:border-[#0d4f3c] hover:bg-[#0d4f3c]/5 hover:text-[#0d4f3c]"
                >
                  {a.symbol}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
