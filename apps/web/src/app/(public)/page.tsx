import Link from "next/link"

export default function HomePage() {
  return (
    <div className="mx-auto max-w-4xl px-6">
      {/* 1. Hero */}
      <section className="py-16">
        <h1 className="font-title text-4xl tracking-wide text-zinc-900">
          See the shift before the move
        </h1>
        <p className="mt-6 text-lg text-zinc-600">
          Regime classification, escalation as an instability signal, and
          cross-timeframe consensus across markets.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/markets"
            className="rounded bg-[#0d4f3c] px-6 py-3 font-medium text-white hover:bg-[#165a45]"
          >
            Explore assets
          </Link>
          <Link
            href="/signup"
            className="rounded border border-zinc-300 px-6 py-3 font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Sign up
          </Link>
          <Link
            href="/login"
            className="rounded border border-zinc-300 px-6 py-3 font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Log in
          </Link>
        </div>
      </section>

      {/* 2. Value Proposition */}
      <section className="border-t border-zinc-200 py-16">
        <h2 className="text-xl font-semibold text-zinc-900">
          What we deliver
        </h2>
        <div className="mt-8 grid gap-8 sm:grid-cols-2">
          <div>
            <h3 className="font-medium text-zinc-900">
              Regime classification
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              Clear labels for market state—trending, choppy, shock, or
              transition—with confidence scores.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-zinc-900">
              Escalation percentile
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              Instability signal that flags when conditions are heating up,
              before moves materialize.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-zinc-900">
              Cross-timeframe consensus
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              Agreement across timeframes—5 TF for macro, 2 TF for
              earnings—so you see alignment or divergence.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-zinc-900">
              Workflow
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              Watchlists, alerts on bucket or regime changes, and saved
              screens for your process.
            </p>
          </div>
        </div>
      </section>

      {/* 3. How It Works */}
      <section className="border-t border-zinc-200 py-16">
        <h2 className="text-xl font-semibold text-zinc-900">
          How it works
        </h2>
        <ol className="mt-8 space-y-6">
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-sm font-medium text-zinc-700">
              1
            </span>
            <div>
              <p className="font-medium text-zinc-900">Market data in</p>
              <p className="mt-1 text-sm text-zinc-600">
                Price and volume feed the engine per symbol and timeframe.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-sm font-medium text-zinc-700">
              2
            </span>
            <div>
              <p className="font-medium text-zinc-900">Regime + confidence</p>
              <p className="mt-1 text-sm text-zinc-600">
                Each timeframe gets a regime label and stability score.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-sm font-medium text-zinc-700">
              3
            </span>
            <div>
              <p className="font-medium text-zinc-900">Escalation bucket</p>
              <p className="mt-1 text-sm text-zinc-600">
                Instability percentile and bucket (low, medium, high) per
                symbol.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-sm font-medium text-zinc-700">
              4
            </span>
            <div>
              <p className="font-medium text-zinc-900">Consensus</p>
              <p className="mt-1 text-sm text-zinc-600">
                Agreement ratio across timeframes.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-sm font-medium text-zinc-700">
              5
            </span>
            <div>
              <p className="font-medium text-zinc-900">Alerts and screens</p>
              <p className="mt-1 text-sm text-zinc-600">
                Set triggers on bucket, regime, or consensus; build
                watchlists and saved screens.
              </p>
            </div>
          </li>
        </ol>
      </section>

      {/* 4. Coverage */}
      <section className="border-t border-zinc-200 py-16">
        <h2 className="text-xl font-semibold text-zinc-900">
          Coverage
        </h2>
        <div className="mt-8 grid gap-8 sm:grid-cols-2">
          <div className="rounded border border-zinc-200 bg-zinc-50/50 p-6">
            <h3 className="font-medium text-zinc-900">
              Core Macro
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              FX, Indices, Commodities, Crypto, Rates. Five timeframes:
              15m, 1h, 4h, 1d, 1w.
            </p>
            <p className="mt-2 text-sm text-zinc-500">
              ~37 symbols
            </p>
          </div>
          <div className="rounded border border-zinc-200 bg-zinc-50/50 p-6">
            <h3 className="font-medium text-zinc-900">
              Earnings Universe
            </h3>
            <p className="mt-2 text-sm text-zinc-600">
              US equities with event-aware framework. Daily and Weekly
              timeframes only.
            </p>
            <p className="mt-2 text-sm text-zinc-500">
              ~1,518 symbols
            </p>
          </div>
        </div>
        <p className="mt-6 text-sm text-zinc-500">
          ~1,565 total symbols
        </p>
      </section>

      {/* 5. Trust / Audit */}
      <section className="border-t border-zinc-200 py-16">
        <h2 className="text-xl font-semibold text-zinc-900">
          Transparency
        </h2>
        <p className="mt-4 text-sm text-zinc-600">
          We disclose engine version, snapshot ID, code version, data
          timestamps, conceptual metric definitions, escalation approach,
          and classifier logic. Not the recipe—coefficients, weights, or
          thresholds stay proprietary.
        </p>
        <div className="mt-6 flex flex-wrap gap-4">
          <Link
            href="/methodology"
            className="text-sm font-medium text-[#0d4f3c] hover:underline"
          >
            Methodology
          </Link>
          <Link
            href="/audit"
            className="text-sm font-medium text-[#0d4f3c] hover:underline"
          >
            Audit
          </Link>
        </div>
      </section>

      {/* 6. Pricing CTA */}
      <section className="border-t border-zinc-200 py-16">
        <p className="text-zinc-600">
          Free and paid tiers available.
        </p>
        <Link
          href="/pricing"
          className="mt-4 inline-block rounded bg-[#0d4f3c] px-6 py-3 font-medium text-white hover:bg-[#165a45]"
        >
          View pricing
        </Link>
      </section>
    </div>
  )
}
