import { LayoutEquities } from "@/components/symbol/LayoutEquities"
import { LayoutFX } from "@/components/symbol/LayoutFX"
import { LayoutCrypto } from "@/components/symbol/LayoutCrypto"
import { LayoutCommodities } from "@/components/symbol/LayoutCommodities"
import { LayoutFixedIncome } from "@/components/symbol/LayoutFixedIncome"
import { riApi } from "@/lib/api"

const LAYOUT_MAP: Record<string, React.ComponentType<{ symbol: string; name: string }>> = {
  US_EQUITY: LayoutEquities,
  US_EQUITY_INDEX: LayoutEquities,
  FX: LayoutFX,
  CRYPTO: LayoutCrypto,
  Commodities: LayoutCommodities,
  "Fixed Income": LayoutFixedIncome,
}

export default async function SymbolPage({
  params,
}: {
  params: Promise<{ symbol: string }>
}) {
  const { symbol } = await params
  let asset
  try {
    asset = await riApi.asset(symbol)
  } catch {
    asset = null
  }

  const ac = asset?.asset_class ?? "US_EQUITY"
  const Layout = LAYOUT_MAP[ac] ?? LayoutEquities
  const name = asset?.name ?? symbol

  return <Layout symbol={symbol.toUpperCase()} name={name} />
}
