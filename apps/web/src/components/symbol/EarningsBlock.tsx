import type { EarningsData } from "@/lib/twelvedata"

type Props = { earnings: EarningsData }

function formatDate(s: string): string {
  try {
    const d = new Date(s)
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return s
  }
}

export function EarningsBlock({ earnings }: Props) {
  const {
    next_date,
    next_time,
    last_date,
    last_eps_estimate,
    last_eps_actual,
    last_surprise_prc,
  } = earnings

  const hasNext = next_date
  const hasLast =
    last_date && (last_eps_actual != null || last_eps_estimate != null)

  if (!hasNext && !hasLast) return null

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6">
      <h2 className="text-sm font-medium text-zinc-500">Earnings</h2>
      <div className="mt-3 space-y-2 text-sm">
        {hasNext && (
          <p className="text-zinc-900">
            Next report: {formatDate(next_date)}
            {next_time && next_time !== "Time Not Supplied" && (
              <span className="ml-1 text-zinc-500">({next_time})</span>
            )}
          </p>
        )}
        {hasLast && (
          <p className="text-zinc-600">
            Last ({formatDate(last_date)}):{" "}
            {last_eps_actual != null ? (
              <>
                EPS ${last_eps_actual.toFixed(2)}
                {last_eps_estimate != null && (
                  <span className="text-zinc-500">
                    {" "}
                    (est. ${last_eps_estimate.toFixed(2)})
                  </span>
                )}
                {last_surprise_prc != null && (
                  <span
                    className={
                      last_surprise_prc >= 0 ? "text-emerald-600" : "text-rose-600"
                    }
                  >
                    {" "}
                    {last_surprise_prc >= 0 ? "+" : ""}
                    {last_surprise_prc.toFixed(1)}%
                  </span>
                )}
              </>
            ) : (
              last_eps_estimate != null && `est. $${last_eps_estimate.toFixed(2)}`
            )}
          </p>
        )}
      </div>
    </div>
  )
}
