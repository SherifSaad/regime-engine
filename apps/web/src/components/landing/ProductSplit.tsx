import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatInt } from "@/lib/landing-data"
import type { Stats } from "@/lib/api"

const CORE_BULLETS = [
  "Risk-on/off map",
  "Regime timeline",
  "Escalation percentile",
  "Alerts-ready",
]

const EARNINGS_BULLETS = [
  "Earnings calendar view",
  "Rank by escalation",
  "Watchlists",
  "Event windows",
]

export function ProductSplit({ stats }: { stats: Stats | null }) {
  const earningsCount = stats?.earnings_count ?? stats?.assets_total ?? 0
  return (
    <section id="core" className="py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-2">
          <Card className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-xl">Core Market Intelligence</CardTitle>
              <p className="text-sm text-zinc-600">
                Macro regimes across broad assets
              </p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {CORE_BULLETS.map((b) => (
                  <li key={b} className="flex items-center gap-2 text-sm text-zinc-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                    {b}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button asChild>
                <Link href="/app#core">Explore Core</Link>
              </Button>
            </CardFooter>
          </Card>

          <Card id="earnings" className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-xl">Earnings Intelligence</CardTitle>
              <p className="text-sm text-zinc-600">
                Scan {formatInt(earningsCount)} stocks for pre-earnings instability
              </p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {EARNINGS_BULLETS.map((b) => (
                  <li key={b} className="flex items-center gap-2 text-sm text-zinc-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                    {b}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button asChild>
                <Link href="/app#earnings">Explore Earnings</Link>
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    </section>
  )
}
