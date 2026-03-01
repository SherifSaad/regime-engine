import type { LogoData } from "@/lib/twelvedata"

type Props = {
  symbol: string
  name: string
  assetClassLabel: string
  logo?: LogoData | null
  sector?: string
  industry?: string
}

export function AssetHeader({
  symbol,
  name,
  assetClassLabel,
  logo,
  sector,
  industry,
}: Props) {
  const imgUrl = logo?.url ?? logo?.logo_base

  return (
    <div className="flex items-start gap-4">
      {imgUrl && (
        <img
          src={imgUrl}
          alt=""
          className="h-12 w-12 shrink-0 rounded-lg object-contain"
        />
      )}
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-zinc-900">{symbol}</h1>
        <p className="text-zinc-600">{name}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="inline-block rounded bg-zinc-200 px-2 py-0.5 text-xs">
            {assetClassLabel}
          </span>
          {(sector || industry) && (
            <span className="text-xs text-zinc-500">
              {[sector, industry].filter(Boolean).join(" · ")}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
