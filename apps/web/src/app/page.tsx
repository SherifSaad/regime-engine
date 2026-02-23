import { riApi } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { LockedCard } from "@/components/locked-card"

function formatInt(n: number) {
  return new Intl.NumberFormat().format(n)
}

function formatPct(x: number) {
  return `${Math.round(x * 100)}%`
}

type LeaderItem = {
  symbol: string
  asset_class: string
  name: string
  score: number
  updated_utc: string
}

export default async function HomePage() {
  const [stats, assets] = await Promise.all([riApi.stats(), riApi.assets()])

  // Build a deterministic "Top Escalations" leaderboard from registry data only (no hardcoding)
  // We use per-asset compute calc_units as a proxy for "engine activity", because we do NOT yet
  // have a standardized cross-TF consensus endpoint exposed.
  // This will later be replaced with consensus_latest once the compute contract is finalized.
  const leaders: LeaderItem[] = assets
    .filter((a) => a.has_compute)
    .map((a) => ({
      symbol: a.symbol,
      asset_class: a.asset_class,
      name: a.name ?? a.symbol,
      score: a.compute?.calc_units ?? 0,
      updated_utc: a.updated_utc,
    }))
    .sort((x, y) => y.score - x.score)
    .slice(0, 10)

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      {/* NAV */}
      <header className="sticky top-0 z-20 border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-8 py-5">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-xl border bg-gradient-to-br from-zinc-50 to-zinc-200" />
            <div className="text-xl font-semibold tracking-tight">
              Regime Intelligence
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="ghost" asChild>
              <a href="/explore">Explore Free</a>
            </Button>
            <Button variant="outline" asChild>
              <a href="/app">Dashboard</a>
            </Button>
            <Button asChild>
              <a href="/signup">Join Free</a>
            </Button>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative">
        {/* subtle "wow" background (no hardcoded images, pure CSS) */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-gradient-to-b from-zinc-100 to-white blur-3xl" />
          <div className="absolute bottom-[-120px] right-[-120px] h-[360px] w-[360px] rounded-full bg-zinc-100 blur-3xl" />
          <div className="absolute bottom-[-140px] left-[-140px] h-[360px] w-[360px] rounded-full bg-zinc-100 blur-3xl" />
        </div>

        <div className="mx-auto max-w-7xl px-8 pt-20 pb-14">
          <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
            <div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">Deterministic</Badge>
                <Badge variant="secondary">Explainable</Badge>
                <Badge variant="secondary">Audit-ready</Badge>
                <Badge variant="secondary">Multi-timeframe</Badge>
              </div>

              <h1 className="mt-6 text-5xl font-bold leading-tight tracking-tight">
                Regime analysis taken to a new level.
              </h1>

              <p className="mt-6 text-lg text-zinc-600">
                A probabilistic hazard dashboard — not an indicator, not a black box.
                We quantify percentile-based stress risk across assets and timeframes
                using transparent, reproducible logic.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Button size="lg" asChild>
                  <a href="/explore">Explore Free</a>
                </Button>
                <Button variant="outline" size="lg" asChild>
                  <a href="/methodology">See how it works</a>
                </Button>
              </div>

              <div className="mt-10 flex flex-wrap gap-2">
                {stats.asset_classes.map((c) => (
                  <Badge key={c} variant="outline">
                    {c}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Live Stats + Hook */}
            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle>Live Engine Stats</CardTitle>
                <div className="text-sm text-zinc-500">
                  Built from your real registry (auto-updates as assets grow).
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-2 gap-6">
                  <Stat label="Assets tracked" value={formatInt(stats.assets_total)} />
                  <Stat label="Asset classes" value={formatInt(stats.asset_classes.length)} />
                  <Stat label="Timeframes" value={formatInt(stats.timeframes.length)} />
                  <Stat label="Bars analyzed" value={formatInt(stats.bars_total)} />
                </div>

                <Separator />

                <div>
                  <div className="text-sm text-zinc-500">
                    Transparent calculation units
                  </div>
                  <div className="mt-2 text-3xl font-bold">
                    {formatInt(stats.calc_units_total)}
                  </div>
                  <div className="mt-2 text-xs text-zinc-500">
                    Derived from compute tables (rows × output columns). No guessing.
                  </div>
                </div>

                <div className="text-xs text-zinc-400">
                  Generated: {stats.generated_utc}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* SECTION: Top Escalations (hook people to "check daily") */}
      <section className="mx-auto max-w-7xl px-8 pb-10">
        <div className="flex items-end justify-between gap-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Today&apos;s Board</h2>
            <p className="mt-2 text-sm text-zinc-600">
              A daily snapshot that gives people a reason to come back.
              (This will become a true hazard/consensus leaderboard once the consensus endpoint is exposed.)
            </p>
          </div>
          <Button variant="outline" asChild>
            <a href="/explore">Open Free Explorer</a>
          </Button>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Top assets by engine activity</CardTitle>
              <div className="text-sm text-zinc-500">
                Dynamic list; updates automatically as compute refreshes.
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {leaders.map((x, idx) => (
                  <div
                    key={x.symbol}
                    className="flex items-center justify-between rounded-xl border px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 text-sm font-semibold text-zinc-500">
                        #{idx + 1}
                      </div>
                      <div>
                        <div className="font-semibold">
                          {x.symbol}{" "}
                          <span className="text-sm font-normal text-zinc-500">
                            • {x.asset_class}
                          </span>
                        </div>
                        <div className="text-xs text-zinc-500">
                          Updated: {x.updated_utc}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-zinc-500">Score</div>
                      <div className="text-lg font-bold">
                        {formatInt(x.score)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Locked teaser: shows what Pro unlocks */}
          <LockedCard
            title="Pro: Cross-TF Consensus"
            subtitle="Unlock the alignment score + dominant timeframe"
          >
            <div className="space-y-3">
              <div className="rounded-xl border p-4">
                <div className="text-sm text-zinc-500">Consensus score</div>
                <div className="mt-2 text-2xl font-bold">{formatPct(0.93)}</div>
              </div>
              <div className="rounded-xl border p-4">
                <div className="text-sm text-zinc-500">TF alignment</div>
                <div className="mt-2 text-2xl font-bold">4 / 5</div>
              </div>
              <div className="rounded-xl border p-4">
                <div className="text-sm text-zinc-500">Dominant TF</div>
                <div className="mt-2 text-2xl font-bold">1D</div>
              </div>
            </div>
          </LockedCard>
        </div>
      </section>

      {/* SECTION: Free vs Pro (seductive ladder) */}
      <section className="mx-auto max-w-7xl px-8 py-10">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Free vs Pro</h2>
            <p className="mt-2 text-sm text-zinc-600">
              Explore free. Upgrade only when you hit the ceiling.
            </p>
          </div>
          <Badge variant="outline">No ML. No black box. Deterministic only.</Badge>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle>Free</CardTitle>
              <div className="text-sm text-zinc-500">
                Enough to understand the regime context.
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-zinc-700">
              <Feature>Asset class selector + asset selector</Feature>
              <Feature>Multi-timeframe tiles (basic)</Feature>
              <Feature>Limited history depth</Feature>
              <Feature>Basic probability summary</Feature>
              <Button className="mt-2 w-full" asChild>
                <a href="/signup">Join Free</a>
              </Button>
            </CardContent>
          </Card>

          <LockedCard
            title="Pro: Full Probability Tables"
            subtitle="Severity distribution + calibration detail"
          >
            <div className="space-y-3 text-sm">
              <div className="rounded-xl border p-4">
                <div className="text-zinc-500">Outcome class probabilities</div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <div className="rounded-lg border p-2">Mild: 18%</div>
                  <div className="rounded-lg border p-2">Moderate: 27%</div>
                  <div className="rounded-lg border p-2">Severe: 29%</div>
                  <div className="rounded-lg border p-2">Crisis: 14%</div>
                </div>
              </div>
            </div>
          </LockedCard>

          <LockedCard
            title="Pro: Watchlist + Daily Board"
            subtitle="Track your universe and see what changed"
          >
            <div className="space-y-3 text-sm">
              <div className="rounded-xl border p-4">
                <div className="text-zinc-500">Watchlist (example)</div>
                <div className="mt-2 space-y-2">
                  <div className="rounded-lg border p-2">SPY • 1D • HIGH</div>
                  <div className="rounded-lg border p-2">BTCUSD • 4H • HIGH</div>
                  <div className="rounded-lg border p-2">XAUUSD • 1W • MID</div>
                </div>
              </div>
            </div>
          </LockedCard>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t py-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-8 text-sm text-zinc-500 md:flex-row md:items-center md:justify-between">
          <div>© {new Date().getFullYear()} Regime Intelligence</div>
          <div className="flex gap-4">
            <a className="hover:opacity-70" href="/legal">Legal</a>
            <a className="hover:opacity-70" href="/contact">Contact</a>
            <a className="hover:opacity-70" href="/faq">FAQ</a>
          </div>
        </div>
      </footer>
    </main>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  )
}

function Feature({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <div className="mt-1 h-2 w-2 rounded-full bg-zinc-900" />
      <div>{children}</div>
    </div>
  )
}
