/**
 * The 11 core metrics from the regime engine.
 * Used for screener columns and asset layout placeholders.
 */
export const METRICS_11 = [
  "Trend Strength",
  "Vol Regime",
  "Drawdown Pressure",
  "Downside Shock",
  "Asymmetry",
  "Momentum State",
  "Structural Score",
  "Liquidity",
  "Gap Risk",
  "Key-Level Pressure",
  "Breadth Proxy",
] as const

export type MetricKey = (typeof METRICS_11)[number]

export type MetricValue = {
  metric: string
  pct: number
  label?: string
}

export type RegimeState = {
  regime_label?: string
  confidence?: number
  escalation_v2?: number
  metrics_11?: MetricValue[]
}

/** Map metric name to short key for sorting/filtering */
export const METRIC_TO_KEY: Record<string, string> = {
  "Trend Strength": "trend_strength",
  "Vol Regime": "vol_regime",
  "Drawdown Pressure": "drawdown_pressure",
  "Downside Shock": "downside_shock",
  "Asymmetry": "asymmetry",
  "Momentum State": "momentum_state",
  "Structural Score": "structural_score",
  "Liquidity": "liquidity",
  "Gap Risk": "gap_risk",
  "Key-Level Pressure": "key_level_pressure",
  "Breadth Proxy": "breadth_proxy",
}
