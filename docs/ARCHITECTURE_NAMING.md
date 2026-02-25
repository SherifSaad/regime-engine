# Architecture & Naming

## Asset lists

| List | Function | update_frequency | Source | Count |
|------|----------|------------------|--------|-------|
| Core | `core_assets()` | 15min | core_symbols.txt | ~60 |
| Daily | `daily_assets()` | daily | universe_symbols.txt | ~1500 |

Core = poll every 15 min. Overlap (e.g. Mag 7 in both files) gets 15min. Build: `python scripts/build_universe_from_symbols.py`

## Backfill

| Script | Assets | Timeframes | Output |
|--------|--------|------------|--------|
| `backfill_asset_full.py` | core_assets() | 15min, 1h, 4h, 1day, 1week | live.db |
| `backfill_asset_partial.py` | daily_assets() | 1day, 1week | live.db |

Both write to `data/assets/{SYMBOL}/live.db`. Full history via paging (5000/request).

## Storage (one folder per asset)

```
data/assets/{SYMBOL}/
  live.db           # raw bars (backfill)
  frozen_*.db       # bars snapshot (pipeline)
  compute.db       # regime, escalation
  bars/            # Parquet (canonical)
    1day/
    1week/
    15min/  # core only
    1h/
    4h/
```

## Migrate

`migrate_live_to_parquet.py --all` migrates core + daily symbols from live.db → Parquet (writes to `data/assets/{SYMBOL}/bars/`).

## Schedulers

| Scheduler | Assets | Timeframes | Frequency |
|-----------|--------|------------|-----------|
| `scheduler_core.py` | core_assets() | 15min, 1h, 4h, 1day, 1week | Every 15 min |
| `scheduler_daily.py` | daily_assets() | 1day, 1week | Once/day (~17:30 EST) |

Both: fetch → Parquet → compute_asset_full → compute.db.

## Data flow

```
Backfill (core):    Twelve Data → live.db → migrate → Parquet → compute_asset_full → compute.db
Backfill (daily):   Twelve Data → live.db → migrate → Parquet → compute_asset_full → compute.db
Scheduler (core):   Twelve Data → Parquet (append) → compute_asset_full → compute.db
Scheduler (daily):  Twelve Data → Parquet (append) → compute_asset_full → compute.db
```

## Deprecated

- `scheduler_real_time.py` → use `scheduler_core.py`
- `scheduler_earnings.py` → use `scheduler_daily.py`
- `real_time_assets()` → use `core_assets()`
