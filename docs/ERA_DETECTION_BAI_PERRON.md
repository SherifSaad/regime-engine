# Bai–Perron Era Detection

**Purpose:** Detect structural breaks in log(126-day realized volatility). Eras are asset-class specific, derived from canonical benchmarks. Frozen for percentile conditioning.

---

## Constraints (Frozen)

| Parameter | Value | Notes |
|-----------|-------|-------|
| ε | 1e-12 | log(RV_126 + ε) |
| RV window | 126 | Rolling realized volatility |
| Min segment | 504 | ~2 years trading days |
| Break model | **Mean only** | Not variance |
| Scope | **Asset-class** | Not per-symbol |

---

## Asset Class → Benchmark

| Asset Class | Benchmark |
|-------------|-----------|
| EQUITIES_US | SPY |
| CREDIT_HY | HYG |
| CREDIT_IG | LQD |
| RATES_LONG | TLT |
| RATES_INTERMEDIATE | IEF |
| FX_USD_PROXY | EURUSD |
| FX_MAJORS | EURUSD |
| COMMODITIES_ENERGY | WTIUSD |
| COMMODITIES_METALS | XAUUSD |
| CRYPTO | BTCUSD |

Breakpoints are derived from the benchmark and apply to the entire asset class. Data: Parquet via BarsProvider (preferred); CSV fallback in `ASSET_FILES` (hyg_clean.csv, lqd_clean.csv, etc.) when Parquet unavailable.

---

## Pipeline

1. Load benchmark bars (Parquet or CSV fallback)
2. Compute 126-day rolling RV from log returns
3. log_RV = log(RV_126 + 1e-12)
4. Bai–Perron: detect breaks in **mean** of log_RV
5. BIC for model selection (number of breaks)
6. Output breakpoints as era boundaries

---

## Outputs

| File | Description |
|------|--------------|
| `era_boundaries.csv` | Era boundary table (asset_class, benchmark, era_index, start_date, end_date) |
| `eras_{AC}.json` | Params + break indices + break dates + data_hash |
| `bic_{AC}.csv` | BIC comparison table (k_breaks, bic) |
| `eras_{AC}.png` | Plot with log(RV) and breakpoint lines |
| `era_metadata_frozen.json` | Frozen metadata with data hash per asset class |

---

## Usage

```bash
python scripts/detect_eras_bai_perron.py
python scripts/detect_eras_bai_perron.py --asset-class CRYPTO
```

**Plot:** Requires `pip install matplotlib` (or `pip install regime-engine[era]`).

---

## Percentile Conditioning

Use `era_boundaries.csv` or `eras_{AC}.json` to condition percentiles within each era. No intersections. No window confusion.
