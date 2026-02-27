import Link from "next/link"
import { Button } from "@/components/ui/button"

export function FinalCTA() {
  return (
    <section className="border-t border-zinc-200 bg-zinc-50/50 py-20 sm:py-28">
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
        <h2 className="text-3xl font-bold tracking-tight text-zinc-900 sm:text-4xl">
          See the shift before the move.
        </h2>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Button size="lg" asChild>
            <Link href="/app">Open App</Link>
          </Button>
          <Button variant="outline" size="lg" asChild>
            <Link href="/request-access">Request Access</Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
