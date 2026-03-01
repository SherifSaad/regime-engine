import type { AnalystData } from "@/lib/twelvedata"

type Props = { analyst: AnalystData }

export function AnalystBlock({ analyst }: Props) {
  const {
    strong_buy,
    buy,
    hold,
    sell,
    strong_sell,
    rating,
    price_target_high,
    price_target_median,
    price_target_low,
    price_target_average,
    price_target_current,
  } = analyst

  const hasRecs =
    [strong_buy, buy, hold, sell, strong_sell].some((n) => n != null && n > 0) ||
    rating != null
  const hasTarget =
    price_target_median != null ||
    price_target_average != null ||
    (price_target_high != null && price_target_low != null)

  if (!hasRecs && !hasTarget) return null

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">Analyst</h2>
      <div className="mt-3 space-y-4">
        {hasRecs && (
          <div>
            <div className="flex flex-wrap gap-3 text-xs">
              {strong_buy != null && strong_buy > 0 && (
                <span className="text-emerald-600">
                  Strong Buy {strong_buy}
                </span>
              )}
              {buy != null && buy > 0 && (
                <span className="text-emerald-500">Buy {buy}</span>
              )}
              {hold != null && hold > 0 && (
                <span className="text-zinc-600">Hold {hold}</span>
              )}
              {sell != null && sell > 0 && (
                <span className="text-amber-600">Sell {sell}</span>
              )}
              {strong_sell != null && strong_sell > 0 && (
                <span className="text-rose-600">Strong Sell {strong_sell}</span>
              )}
            </div>
            {rating != null && (
              <p className="mt-1 text-sm text-zinc-600">
                Consensus: {rating.toFixed(1)} / 10
              </p>
            )}
          </div>
        )}
        {hasTarget && (
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            {(price_target_median != null || price_target_average != null) && (
              <span className="text-zinc-900">
                Target: $
                {(price_target_median ?? price_target_average ?? 0).toFixed(0)}
              </span>
            )}
            {price_target_high != null && price_target_low != null && (
              <span className="text-zinc-500">
                Range ${price_target_low.toFixed(0)}–${price_target_high.toFixed(0)}
              </span>
            )}
            {price_target_current != null && (
              <span className="text-zinc-500">
                Current ${price_target_current.toFixed(2)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
