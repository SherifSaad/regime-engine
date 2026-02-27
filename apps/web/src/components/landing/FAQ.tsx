const FAQ_ITEMS = [
  {
    q: "Is this buy/sell signals?",
    a: "No.",
  },
  {
    q: "Does it predict direction?",
    a: "No. It measures instability and regime shifts, not price direction.",
  },
  {
    q: "Is it AI?",
    a: "Deterministic, not ML. Transparent logic, no black box.",
  },
  {
    q: "What markets?",
    a: "Core assets (FX, commodities, indices, crypto) plus US earnings universe (1,550 symbols).",
  },
  {
    q: "How often updated?",
    a: "15-minute and daily.",
  },
  {
    q: "Is this financial advice?",
    a: "No.",
  },
]

export function FAQ() {
  return (
    <section id="faq" className="border-t border-zinc-200 py-16 sm:py-24">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 className="text-center text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl">
          FAQ
        </h2>

        <dl className="mt-12 space-y-8">
          {FAQ_ITEMS.map((item) => (
            <div key={item.q}>
              <dt className="font-semibold text-zinc-900">{item.q}</dt>
              <dd className="mt-2 text-zinc-600">{item.a}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
