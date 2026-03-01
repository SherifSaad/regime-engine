import Link from "next/link"

export default function AuditPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-2xl font-bold text-zinc-900">
        Audit / Transparency
      </h1>
      <p className="mt-2 text-zinc-600">
        We disclose engine version, snapshot ID, code version, data
        timestamps, conceptual metric definitions, escalation approach,
        and classifier logic. We do not disclose coefficients,
        weighting, proprietary thresholds, or the full recipe.
      </p>

      <div className="mt-10 space-y-8">
        <section className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-semibold text-zinc-900">
            Engine Version
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            V1. Standard V2.2 metrics locked. (Placeholder: version badge
            when manifest available.)
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-semibold text-zinc-900">
            Snapshot &amp; Code
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            Snapshot ID (YYYY-MM-DD), code version (git hash), built_utc.
            Populated from manifest when available.
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-semibold text-zinc-900">
            Metric Definitions (Conceptual)
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            10 metrics: MB, RL, BP, DSR, SS, VRS, Momentum, LQ, IIX, ASM.
            Key Levels support SS/BP. Conceptual descriptions only—no
            coefficients or thresholds.
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-semibold text-zinc-900">
            Escalation Approach
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            esc_raw, esc_pctl_era_adj, esc_bucket. Buckets: LOW &lt;60%,
            MED 60–85%, HIGH ≥85%. Era-adjusted percentile methodology.
          </p>
        </section>

        <section className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-semibold text-zinc-900">
            Classifier Logic
          </h2>
          <p className="mt-2 text-sm text-zinc-600">
            Regime labels: SHOCK, PANIC_RISK, TRENDING_BULL, TRENDING_BEAR,
            CHOP_RISK, TRANSITION, TRANSITION_BREAKOUT_SETUP. Logic
            described conceptually—no proprietary thresholds.
          </p>
        </section>
      </div>

      <div className="mt-10 flex gap-4">
        <Link
          href="/methodology"
          className="text-sm font-medium text-[#0d4f3c] hover:underline"
        >
          Methodology
        </Link>
        <Link
          href="/"
          className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
        >
          Home
        </Link>
      </div>
    </div>
  )
}
