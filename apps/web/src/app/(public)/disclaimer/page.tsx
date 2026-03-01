import Link from "next/link"

export default function DisclaimerPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
        ← Back
      </Link>
      <h1 className="mt-6 text-3xl font-bold tracking-tight">Disclaimer</h1>
      <div className="mt-8 space-y-4 text-zinc-600">
        <p>
          Regime Intelligence is not investment advice. It does not provide
          buy, sell, or hold recommendations. It does not predict price
          direction.
        </p>
        <p>
          Our outputs measure distribution instability and regime shifts. They
          are not directional forecasts. Past validation does not guarantee
          future results.
        </p>
        <p>
          Consult a qualified professional before making investment decisions.
        </p>
      </div>
    </div>
  )
}
