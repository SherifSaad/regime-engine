import { AssetPageNav } from "./AssetPageNav"
import { AssetHeader } from "./AssetHeader"
import { MarketSnapshotBlock } from "./MarketSnapshotBlock"
import { MetricsBlock } from "./MetricsBlock"
import { ProfileBlock } from "./ProfileBlock"
import type { AssetLayoutProps } from "@/lib/assetLayoutTypes"

const TF_5 = ["15m", "1h", "4h", "1d", "1w"]

export function LayoutCommodities({ symbol, name, assetClass, quote, marketCap, nextEarningsDate, logo, profile, isPaid = false, regimeByTf = {} }: AssetLayoutProps) {
  return (
    <div>
      <AssetPageNav symbol={symbol} assetClass={assetClass} />
      <div className="mb-6">
        <AssetHeader
          symbol={symbol}
          name={name}
          assetClassLabel="Commodities"
          logo={logo}
          sector={profile?.sector}
          industry={profile?.industry}
        />
      </div>

      <div className="mb-6">
        <MarketSnapshotBlock
          price={quote?.close}
          changePct={quote?.percent_change}
          volume={quote?.volume}
          dayRangeLow={quote?.low ? parseFloat(quote.low) : null}
          dayRangeHigh={quote?.high ? parseFloat(quote.high) : null}
          marketCap={marketCap}
          nextEarningsDate={nextEarningsDate}
          format="currency"
        />
      </div>

      <div className="mb-6">
        <MetricsBlock timeframes={TF_5} regimeByTf={regimeByTf} isPaid={isPaid} />
      </div>

      {profile && (
        <div className="mb-6">
          <ProfileBlock profile={profile} />
        </div>
      )}
    </div>
  )
}
