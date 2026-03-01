export default function AlertsCenterPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900">Alerts Center</h1>
      <p className="mt-1 text-sm text-zinc-500">
        Bucket change · Regime change · Percentile threshold · Consensus
        threshold · Watchlists · Saved screens
      </p>

      <div className="mt-8 space-y-6">
        {/* Trigger types */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-medium text-zinc-900">Trigger Types</h2>
          <ul className="mt-4 space-y-2 text-sm text-zinc-600">
            <li>
              <strong>Escalation bucket change</strong> — LOW ↔ MED ↔ HIGH
            </li>
            <li>
              <strong>Regime label change</strong> — e.g. TRENDING_BULL →
              CHOP_RISK
            </li>
            <li>
              <strong>Percentile threshold</strong> — User-defined (e.g.
              alert when esc_pctl ≥ 85)
            </li>
            <li>
              <strong>Consensus threshold</strong> — User-defined (e.g.
              alert when 5-TF agreement ≥ 80%)
            </li>
          </ul>
        </div>

        {/* Watchlists */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-medium text-zinc-900">Watchlists</h2>
          <p className="mt-2 text-sm text-zinc-500">
            Group symbols and set alerts per watchlist. (Placeholder—no
            auth yet.)
          </p>
        </div>

        {/* Saved screens */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-medium text-zinc-900">Saved Screens</h2>
          <p className="mt-2 text-sm text-zinc-500">
            Save filter and view configurations for quick access.
            (Placeholder—no auth yet.)
          </p>
        </div>

        {/* Active alerts placeholder */}
        <div className="rounded-lg border border-zinc-200 bg-white p-6">
          <h2 className="font-medium text-zinc-900">Active Alerts</h2>
          <p className="mt-2 text-sm text-zinc-500">
            (Placeholder—alerts list when wired)
          </p>
        </div>
      </div>
    </div>
  )
}
