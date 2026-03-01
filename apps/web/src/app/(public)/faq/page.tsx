import Link from "next/link"

const FAQ_ITEMS = [
  { q: "Is this buy/sell signals?", a: "No." },
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
    a: "Core assets (FX, commodities, indices, crypto) plus US earnings universe.",
  },
  { q: "How often updated?", a: "15-minute and daily." },
  { q: "Is this financial advice?", a: "No." },
]

export default function FAQPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
        ← Back
      </Link>
      <h1 className="mt-6 text-3xl font-bold tracking-tight">FAQ</h1>
      <dl className="mt-12 space-y-8">
        {FAQ_ITEMS.map((item) => (
          <div key={item.q}>
            <dt className="font-semibold text-zinc-900">{item.q}</dt>
            <dd className="mt-2 text-zinc-600">{item.a}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
