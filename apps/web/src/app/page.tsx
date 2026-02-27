import Link from "next/link"

export default function HomePage() {
  return (
    <div>
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-zinc-900">Regime Intelligence</h1>
        <h2 className="mt-2 text-xl font-semibold text-zinc-700">See the shift before the move</h2>
        <p className="mt-4 text-zinc-600">
          Institutional-grade regime intelligence across markets and earnings. Focus on regime shifts + instability detection + earnings intelligence.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-6">
        <div className="rounded-2xl bg-gradient-to-br from-[#0d4f3c] to-[#165a45] p-6 text-white shadow-lg">
          <h2 className="font-semibold">Regime Overview</h2>
          <p className="mt-2 text-sm text-white/80">Required: 10 — Current: 4</p>
          <div className="mt-4 h-2 w-40 rounded-full bg-white/20">
            <div className="h-full rounded-full bg-[#22c55e]" style={{ width: "40%" }} />
          </div>
          <div className="mt-4 text-2xl font-bold">64+</div>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="font-semibold text-zinc-900">Asset Classes</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {["FX", "Commodities", "Indices", "Crypto"].map((label) => (
              <span key={label} className="rounded-full bg-[#0d4f3c]/10 px-4 py-1.5 text-sm font-medium text-[#0d4f3c]">
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="font-semibold text-zinc-900">Total Escalation Score</h2>
          <p className="mt-2 text-4xl font-bold text-[#0d4f3c]">72.4</p>
          <p className="text-sm text-zinc-500">Cross-TF consensus</p>
          <button className="mt-4 rounded-lg bg-[#22c55e] px-4 py-2 font-medium text-white hover:bg-[#1ea34e] transition-colors">Explore</button>
          <button className="ml-2 rounded-lg border border-zinc-300 px-4 py-2 font-medium hover:bg-zinc-50 transition-colors">Alerts</button>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="font-semibold text-zinc-900">Escalation by Timeframe</h2>
          <div className="mt-4 flex items-end gap-3">
            {["15m", "1h", "4h", "1d", "1w"].map((tf, i) => (
              <div key={tf} className="flex flex-col items-center gap-1">
                <div className="w-10 rounded-t bg-gradient-to-t from-[#0d4f3c] to-[#22c55e]" style={{ height: `${40 + i * 14}px` }} />
                <span className="text-xs font-medium text-zinc-500">{tf}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="font-semibold text-zinc-900">Explore symbols</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { sym: "AAPL", label: "Apple" },
              { sym: "SPY", label: "S&P 500" },
              { sym: "EURUSD", label: "Euro" },
              { sym: "BTCUSD", label: "Bitcoin" },
              { sym: "XAUUSD", label: "Gold" },
            ].map(({ sym, label }) => (
              <a key={sym} href={`/symbol/${sym}`} className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-[#0d4f3c] hover:text-white transition-colors">
                {sym}
              </a>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
          <h2 className="font-semibold text-zinc-900">Regime Alerts</h2>
          <div className="mt-4 space-y-2">
            {[
              { sym: "SPY", pct: 50, color: "bg-amber-100 text-amber-800" },
              { sym: "XAUUSD", pct: 80, color: "bg-red-100 text-red-800" },
              { sym: "BTCUSD", pct: 60, color: "bg-amber-100 text-amber-800" },
            ].map(({ sym, pct, color }) => (
              <div key={sym} className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2">
                <span className="font-medium">{sym}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <footer className="pt-6 text-sm text-zinc-500">
        <Link href="/disclaimer" className="underline hover:text-zinc-700">Disclaimer</Link>
        {" · "}
        <Link href="/terms" className="underline hover:text-zinc-700">Terms</Link>
        {" · "}
        <Link href="/faq" className="underline hover:text-zinc-700">FAQ</Link>
      </footer>
    </div>
  )
}
