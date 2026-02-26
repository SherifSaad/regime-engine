# Timeframe Convention

**Purpose:** Canonical timeframe names and aliases. Use when normalizing API input or storing bars.

## Canonical timeframes

All bar folders and API calls use these names:

| Canonical | Twelve Data | Notes |
|-----------|-------------|-------|
| 15min     | 15min       |       |
| 1h        | 1h          | not 1hour |
| 4h        | 4h          |       |
| 1day      | 1day        | not 1d |
| 1week     | 1week       | not 1w |

## Aliases (normalized on input)

- `1d` → `1day`
- `1w` → `1week`
- `1hour` → `1h`
- `15mins` → `15min`
- `4hour`, `4hours` → `4h`

`BarsProvider` and `normalize_timeframe()` apply this at storage boundaries.

## Asset tiers

| Tier | Timeframes | Scheduler |
|------|------------|-----------|
| Core | 15min, 1h, 4h, 1day, 1week | scheduler_core |
| Daily | 1day, 1week | scheduler_daily |

## Cleanup

Remove empty legacy folders (1d, 1w, 1min):

```bash
python scripts/cleanup_legacy_bar_folders.py --dry-run  # preview
python scripts/cleanup_legacy_bar_folders.py             # apply
```
