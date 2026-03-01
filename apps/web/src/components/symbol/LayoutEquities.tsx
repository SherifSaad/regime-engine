import { AssetPageNav } from "./AssetPageNav"
import { AssetHeader } from "./AssetHeader"
import { MarketSnapshotBlock } from "./MarketSnapshotBlock"
import { MetricsBlock } from "./MetricsBlock"
import { ProfileBlock } from "./ProfileBlock"
import { StatisticsBlock } from "./StatisticsBlock"
import { EarningsBlock } from "./EarningsBlock"
import { AnalystBlock } from "./AnalystBlock"
import type { AssetLayoutProps } from "@/lib/assetLayoutTypes"

const TF_5 = ["15m", "1h", "4h", "1d", "1w"]
const TF_2 = ["1d", "1w"]

export function LayoutEquities({
  symbol,
  name,
  assetClass,
  quote,
  marketCap,
  nextEarningsDate,
  logo,
  profile,
  statistics,
  earnings,
  analyst,
  isPaid = false,
  regimeByTf = {},
}: AssetLayoutProps) {
  const isEarnings = assetClass === "US_EQUITY"
  const timeframes = isEarnings ? TF_2 : TF_5
  return (
    <div>
      <AssetPageNav symbol={symbol} assetClass={assetClass} />
      <div className="mb-6">
        <AssetHeader
          symbol={symbol}
          name={name}
          assetClassLabel="Equities"
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
        <MetricsBlock timeframes={timeframes} regimeByTf={regimeByTf} isPaid={isPaid} />
      </div>

      {profile && (
        <div className="mb-6">
          <ProfileBlock profile={profile} />
        </div>
      )}
      {statistics && (
        <div className="mb-6">
          <StatisticsBlock statistics={statistics} />
        </div>
      )}
      {earnings && (
        <div className="mb-6">
          <EarningsBlock earnings={earnings} />
        </div>
      )}
      {analyst && (
        <div className="mb-6">
          <AnalystBlock analyst={analyst} />
        </div>
      )}
    </div>
  )
}
