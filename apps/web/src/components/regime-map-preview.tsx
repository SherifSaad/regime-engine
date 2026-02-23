import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { Asset } from "@/lib/api"

function clamp01(x: number) {
  if (x < 0) return 0
  if (x > 1) return 1
  return x
}

// Deterministic visual mapping: uses available compute intensity as a proxy until
// we expose true hazard/consensus. No hardcoded asset classes or lists.
function intensityToLevel(x: number) {
  // x assumed normalized 0..1
  if (x >= 0.85) return { label: "HIGH", tone: "bg-zinc-900 text-white" }
  if (x >= 0.60) return { label: "ELEVATED", tone: "bg-zinc-200 text-zinc-900" }
  if (x >= 0.35) return { label: "MID", tone: "bg-zinc-100 text-zinc-900" }
  return { label: "LOW", tone: "bg-white text-zinc-700 border" }
}

export function RegimeMapPreview({ assets }: { assets: Asset[] }) {
  // Group assets dynamically by asset_class (no hardcoding)
  const byClass = new Map<string, Asset[]>()
  for (const a of assets) {
    const k = a.asset_class || "UNKNOWN"
    if (!byClass.has(k)) byClass.set(k, [])
    byClass.get(k)!.push(a)
  }

  // Compute a per-class "activity intensity" based on compute.calc_units
  // Normalize by the max across classes for a clean bar scale.
  const classScores = Array.from(byClass.entries()).map(([assetClass, list]) => {
    const computed = list.filter((x) => x.has_compute)
    const score = computed.reduce((acc, x) => acc + (x.compute?.calc_units ?? 0), 0)
    return {
      assetClass,
      assetsTotal: list.length,
      assetsComputed: computed.length,
      score,
    }
  })

  const maxScore = Math.max(1, ...classScores.map((x) => x.score))
  const rows = classScores
    .map((x) => ({ ...x, norm: clamp01(x.score / maxScore) }))
    .sort((a, b) => b.norm - a.norm)

  return (
    <Card className="shadow-sm">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Live Regime Map (Preview)</CardTitle>
          <div className="mt-1 text-sm text-zinc-500">
            Dynamic snapshot across all asset classes. Updates automatically as your registry grows.
          </div>
        </div>
        <Badge variant="outline">No hardcoded lists</Badge>
      </CardHeader>

      <CardContent className="space-y-3">
        {rows.map((r) => {
          const lvl = intensityToLevel(r.norm)
          const barPct = Math.round(r.norm * 100)

          return (
            <div key={r.assetClass} className="rounded-2xl border p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="truncate font-semibold">{r.assetClass}</div>
                  <div className="mt-1 text-xs text-zinc-500">
                    Assets: {r.assetsTotal} • Computed: {r.assetsComputed}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${lvl.tone}`}>
                    {lvl.label}
                  </span>
                  <div className="w-20 text-right text-xs text-zinc-500">{barPct}%</div>
                </div>
              </div>

              <div className="mt-3 h-2 w-full rounded-full bg-zinc-100">
                <div
                  className="h-2 rounded-full bg-zinc-900"
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
