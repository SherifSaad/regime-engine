import Link from "next/link"
import { assetClassDisplayName } from "@/lib/assetTypes"

type Props = {
  symbol: string
  assetClass?: string
}

export function AssetPageNav({ symbol, assetClass }: Props) {
  return (
    <nav className="mb-6 flex flex-wrap items-center gap-2 text-sm">
      <Link href="/" className="text-zinc-500 hover:text-zinc-900">
        Home
      </Link>
      <span className="text-zinc-400">/</span>
      <Link href="/markets" className="text-zinc-500 hover:text-zinc-900">
        Markets
      </Link>
      {assetClass && (
        <>
          <span className="text-zinc-400">/</span>
          <Link
            href={`/markets?asset_class=${encodeURIComponent(assetClass)}`}
            className="text-zinc-500 hover:text-zinc-900"
          >
            {assetClassDisplayName(assetClass)}
          </Link>
        </>
      )}
      <span className="text-zinc-400">/</span>
      <span className="font-medium text-zinc-900">{symbol}</span>
    </nav>
  )
}
