import type { QuoteData } from "@/lib/twelvedata"

type Props = {
  quote: QuoteData
  format?: "currency" | "decimal" | "rate"
}

function formatPrice(value: string, format: Props["format"]): string {
  const n = parseFloat(value)
  if (Number.isNaN(n)) return value
  if (format === "currency") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
  if (format === "rate") return n.toFixed(4)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })
}

export function QuoteBlock({ quote, format = "currency" }: Props) {
  const pct = parseFloat(quote.percent_change)
  const isPositive = !Number.isNaN(pct) && pct >= 0
  const isNegative = !Number.isNaN(pct) && pct < 0

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">Price</h2>
      <p className="mt-1 text-2xl font-bold text-zinc-900">
        {formatPrice(quote.close, format)}
      </p>
      {quote.percent_change && (
        <p
          className={`mt-1 text-sm font-medium ${
            isPositive ? "text-emerald-600" : isNegative ? "text-rose-600" : "text-zinc-600"
          }`}
        >
          {isPositive ? "+" : ""}
          {quote.percent_change}%
        </p>
      )}
      {quote.volume && parseFloat(quote.volume) > 0 && (
        <p className="mt-2 text-xs text-zinc-500">
          Vol: {parseFloat(quote.volume).toLocaleString()}
        </p>
      )}
    </div>
  )
}
