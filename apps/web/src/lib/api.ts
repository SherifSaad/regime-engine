export const API_BASE =
  process.env.NEXT_PUBLIC_RI_API_BASE ?? "http://127.0.0.1:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export type Stats = {
  generated_utc: string;
  assets_total: number;
  assets_with_compute: number;
  bars_total: number;
  compute_rows_total: number;
  calc_units_total: number;
  asset_classes: string[];
  timeframes: string[];
};

export type Asset = {
  symbol: string;
  asset_class: string;
  name: string;
  has_compute: boolean;
  timeframes: string[];
  bars_total: number;
  bars_by_tf: Record<string, number>;
  latest_bar_ts_by_tf: Record<string, string>;
  compute: {
    latest_ts: string | null;
    series_table: string | null;
    rows: number;
    calc_units: number;
  };
  updated_utc: string;
};

export const riApi = {
  stats: () => getJSON<Stats>("/stats"),
  assetClasses: () => getJSON<string[]>("/asset-classes"),
  timeframes: () => getJSON<string[]>("/timeframes"),
  assets: (assetClass?: string) =>
    getJSON<Asset[]>(
      assetClass ? `/assets?asset_class=${encodeURIComponent(assetClass)}` : "/assets"
    ),
  asset: (symbol: string) => getJSON<Asset>(`/asset/${encodeURIComponent(symbol)}`),
};
