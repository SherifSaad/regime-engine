import type { StatisticsData } from "@/lib/twelvedata"

type Props = { statistics: StatisticsData }

function fmtCap(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  return n.toLocaleString()
}

export function StatisticsBlock({ statistics }: Props) {
  const { market_cap, pe, fifty_two_week_high, fifty_two_week_low, dividend_yield } =
    statistics

  const hasData =
    market_cap != null ||
    pe != null ||
    (fifty_two_week_high != null && fifty_two_week_low != null) ||
    dividend_yield != null

  if (!hasData) return null

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">Snapshot</h2>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
        {market_cap != null && (
          <div>
            <span className="text-zinc-500">Market cap</span>
            <p className="font-medium text-zinc-900">${fmtCap(market_cap)}</p>
          </div>
        )}
        {pe != null && (
          <div>
            <span className="text-zinc-500">P/E</span>
            <p className="font-medium text-zinc-900">{pe.toFixed(1)}</p>
          </div>
        )}
        {fifty_two_week_high != null && fifty_two_week_low != null && (
          <div>
            <span className="text-zinc-500">52w range</span>
            <p className="font-medium text-zinc-900">
              ${fifty_two_week_low.toFixed(0)}–${fifty_two_week_high.toFixed(0)}
            </p>
          </div>
        )}
        {dividend_yield != null && (
          <div>
            <span className="text-zinc-500">Div yield</span>
            <p className="font-medium text-zinc-900">
              {dividend_yield.toFixed(2)}%
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
