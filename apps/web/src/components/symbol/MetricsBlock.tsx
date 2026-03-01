"use client"

import type { RegimeState } from "@/lib/metrics"

type Props = {
  timeframes: string[]
  regimeByTf?: Record<string, RegimeState>
  isPaid?: boolean
}

export function MetricsBlock({ timeframes, regimeByTf = {}, isPaid = false }: Props) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6">
      <h2 className="font-semibold text-zinc-900">Regime / Escalation</h2>
      <p className="mt-1 text-xs text-zinc-500">
        Per-timeframe regime state and escalation percentile
      </p>
      <div className="mt-4 flex flex-wrap gap-4">
        {timeframes.map((tf) => {
          const d = regimeByTf[tf]
          const show = isPaid && d?.escalation_v2 != null
          return (
            <div
              key={tf}
              className={`rounded-lg border p-4 min-w-[7rem] ${!show ? "relative overflow-hidden" : ""}`}
            >
              {!show && (
                <div
                  className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-[2px]"
                  aria-hidden
                />
              )}
              <span className="text-xs text-zinc-500">{tf}</span>
              <p className={`mt-1 font-bold ${!show ? "select-none blur-[3px]" : ""}`}>
                {show ? `${Math.round((d.escalation_v2 ?? 0) * 100)}%` : "—"}
              </p>
              {show && d?.regime_label && (
                <p className="mt-0.5 text-xs text-zinc-600">{d.regime_label}</p>
              )}
            </div>
          )
        })}
      </div>
      {!isPaid && (
        <p className="mt-4 text-center text-xs text-zinc-500">
          Upgrade to see regime data
        </p>
      )}
    </div>
  )
}
