const COMPARISONS = [
  {
    title: "Traditional signals",
    subtitle: "RSI, MA cross, etc.",
    verdict: "Late, noisy",
    className: "border-zinc-200",
  },
  {
    title: "Black-box AI",
    subtitle: "ML predictions",
    verdict: "Opaque",
    className: "border-zinc-200",
  },
  {
    title: "Regime Intelligence",
    subtitle: "Distribution instability",
    verdict: "Deterministic, explainable, stress-aware",
    className: "border-zinc-900 bg-zinc-900 text-white",
  },
]

export function Differentiation() {
  return (
    <section className="py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl">
          Not signals. Not predictions. Intelligence.
        </h2>
        <p className="mx-auto mt-4 max-w-2xl text-center text-zinc-600">
          We model distribution instability — up or down — not price targets.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {COMPARISONS.map((item) => (
            <div
              key={item.title}
              className={`rounded-xl border-2 p-6 ${item.className}`}
            >
              <div className="text-sm font-medium opacity-80">{item.subtitle}</div>
              <div className="mt-1 text-lg font-semibold">{item.title}</div>
              <div className="mt-3 text-sm font-medium">{item.verdict}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
