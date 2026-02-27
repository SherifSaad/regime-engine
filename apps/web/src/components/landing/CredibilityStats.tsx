import { formatBars, formatInt } from "@/lib/landing-data"
import type { Stats } from "@/lib/api"

export function CredibilityStats({ stats }: { stats: Stats | null }) {
  const items = stats
    ? [
        { value: formatBars(stats.bars_total), label: "Bars analyzed" },
        {
          value: formatInt(stats.earnings_count ?? stats.assets_total),
          label: "US earnings symbols",
        },
        {
          value: stats.timeframes.join(" / "),
          label: "Multi-timeframe",
        },
        { value: "Era-conditioned", label: "Percentiles" },
      ]
    : [
        { value: "—", label: "Bars analyzed" },
        { value: "—", label: "US earnings symbols" },
        { value: "—", label: "Multi-timeframe" },
        { value: "Era-conditioned", label: "Percentiles" },
      ]

  return (
    <section className="border-y border-zinc-200 bg-zinc-50/50">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-2xl font-bold text-zinc-900 sm:text-3xl">
                {stat.value}
              </div>
              <div className="mt-1 text-sm text-zinc-600">{stat.label}</div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-xs text-zinc-500">
          Not investment advice. Not directional forecasts.
        </p>
      </div>
    </section>
  )
}
