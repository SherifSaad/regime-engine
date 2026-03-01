type Props = {
  price?: string | number | null
  changePct?: string | number | null
  volume?: string | number | null
  dayRangeLow?: number | null
  dayRangeHigh?: number | null
  marketCap?: number | null
  nextEarningsDate?: string | null
  format?: "currency" | "decimal" | "rate"
}

function formatPrice(value: string | number | null | undefined, format: Props["format"]): string {
  if (value == null || value === "") return "—"
  const n = typeof value === "string" ? parseFloat(value) : value
  if (Number.isNaN(n)) return "—"
  if (format === "currency") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
  if (format === "rate") return n.toFixed(4)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
}

export function MarketSnapshotBlock({
  price,
  changePct,
  volume,
  dayRangeLow,
  dayRangeHigh,
  marketCap,
  nextEarningsDate,
  format = "currency",
}: Props) {
  const pct = changePct != null ? (typeof changePct === "string" ? parseFloat(changePct) : changePct) : null
  const isPositive = pct != null && !Number.isNaN(pct) && pct >= 0
  const isNegative = pct != null && !Number.isNaN(pct) && pct < 0

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">Market Snapshot</h2>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-xs text-zinc-500">Price</p>
          <p className="mt-1 text-lg font-semibold text-zinc-900">
            {formatPrice(price, format)}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Change %</p>
          <p className={`mt-1 text-lg font-semibold ${isPositive ? "text-emerald-600" : isNegative ? "text-rose-600" : "text-zinc-700"}`}>
            {pct != null && !Number.isNaN(pct) ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Volume</p>
          <p className="mt-1 text-lg font-semibold text-zinc-900">
            {volume != null && volume !== ""
              ? (typeof volume === "number"
                ? volume.toLocaleString()
                : (() => { const n = parseFloat(String(volume)); return Number.isNaN(n) ? String(volume) : n.toLocaleString() })())
              : "—"}
          </p>
        </div>
        {(dayRangeLow != null || dayRangeHigh != null) && (
          <div>
            <p className="text-xs text-zinc-500">Day Range</p>
            <p className="mt-1 text-sm font-medium text-zinc-700">
              {dayRangeLow != null && dayRangeHigh != null
                ? `${formatPrice(dayRangeLow, format)} – ${formatPrice(dayRangeHigh, format)}`
                : "—"}
            </p>
          </div>
        )}
        {marketCap != null && marketCap > 0 && (
          <div>
            <p className="text-xs text-zinc-500">Market Cap</p>
            <p className="mt-1 text-lg font-semibold text-zinc-900">
              {marketCap >= 1e9 ? `${(marketCap / 1e9).toFixed(2)}B` : marketCap >= 1e6 ? `${(marketCap / 1e6).toFixed(2)}M` : marketCap.toLocaleString()}
            </p>
          </div>
        )}
        {nextEarningsDate && (
          <div>
            <p className="text-xs text-zinc-500">Next Earnings</p>
            <p className="mt-1 text-lg font-semibold text-zinc-900">{nextEarningsDate}</p>
          </div>
        )}
      </div>
    </div>
  )
}
