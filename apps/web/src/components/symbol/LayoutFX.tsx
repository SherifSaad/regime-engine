import Link from "next/link"

type Props = { symbol: string; name: string }

export function LayoutFX({ symbol, name }: Props) {
  return (
    <div>
      <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">← Back</Link>
      <div className="mt-4 mb-6">
        <h1 className="text-2xl font-bold text-zinc-900">{symbol}</h1>
        <p className="text-zinc-600">{name}</p>
        <span className="mt-2 inline-block rounded bg-zinc-200 px-2 py-0.5 text-xs">FX</span>
      </div>

      <div className="mb-6 rounded-xl border bg-white p-6">
        <h2 className="font-semibold text-zinc-900">Rate & Change</h2>
        <p className="mt-2 text-3xl font-bold">1.0850</p>
        <p className="text-green-600">+0.3%</p>
        <p className="mt-2 text-xs text-zinc-500">Session: London / NY</p>
      </div>

      <div className="mb-6 rounded-xl border bg-white p-6">
        <h2 className="font-semibold text-zinc-900">Regime / Escalation</h2>
        <div className="mt-4 flex flex-wrap gap-4">
          {["15m", "1h", "4h", "1d", "1w"].map((tf) => (
            <div key={tf} className="rounded border p-3">
              <span className="text-xs text-zinc-500">{tf}</span>
              <p className="font-bold">58%</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
