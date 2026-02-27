import Link from "next/link"
import { Button } from "@/components/ui/button"
import { RegimeTimelineVisual } from "./RegimeTimelineVisual"
import { formatBars } from "@/lib/landing-data"
import type { Stats } from "@/lib/api"

export function Hero({ stats }: { stats: Stats | null }) {
  const proofChips = stats
    ? [
        `${formatBars(stats.bars_total)} bars analyzed`,
        "Era-conditioned validation",
        "Deterministic (no ML)",
      ]
    : ["Era-conditioned validation", "Deterministic (no ML)"]

  return (
    <section id="hero" className="relative overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <div className="absolute -top-40 left-1/2 h-[480px] w-[800px] -translate-x-1/2 rounded-full bg-gradient-to-b from-zinc-100/80 to-transparent blur-3xl" />
      </div>

      <div className="mx-auto max-w-6xl px-4 pt-16 pb-20 sm:px-6 sm:pt-24 sm:pb-28 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-center lg:gap-16">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl lg:text-[3.25rem]">
              See the shift
              <br />
              before the move
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-zinc-600">
              Institutional-grade regime intelligence across markets and earnings. Focus on regime shifts + instability detection + earnings intelligence.
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              {proofChips.map((chip) => (
                <span
                  key={chip}
                  className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-600"
                >
                  {chip}
                </span>
              ))}
            </div>

            <div className="mt-10 flex flex-wrap gap-3">
              <Button size="lg" asChild>
                <Link href="#core">Explore Core Intelligence</Link>
              </Button>
              <Button variant="outline" size="lg" asChild>
                <Link href="#earnings">Explore Earnings Intelligence</Link>
              </Button>
            </div>
          </div>

          <div className="flex justify-center lg:justify-end">
            <RegimeTimelineVisual />
          </div>
        </div>
      </div>
    </section>
  )
}
