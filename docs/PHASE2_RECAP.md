# PHASE 2 RECAP – Product Vision & Technical Alignment (Feb 24 2026)

## Final Business / Product Requirement (confirmed by user)
We have **two distinct user-facing intelligence offerings** in the same app:

1. **Core Regime Intelligence** (main product, paying clients)
   - ~100 symbols max (currently ~56, will grow to ~100)
   - Symbols: major rates, indices, some FX, some crypto, etc.
   - Must be updated **frequently / near real-time** (every 15 min or as soon as new bars arrive)
   - Full 5 timeframes (15m, 1h, 4h, 1d, 1w) + complete 11-metric regime calculations + escalation
   - These symbols are always "live" and critical

2. **Earnings Intelligence** (extra value / premium extension)
   - ~1500 US stocks (cap > $1B + 90-day vol > 1M)
   - Only **daily + weekly** bars needed
   - Lighter calculations (daily/weekly only)
   - Updated **once per day is sufficient**
   - This is a **bonus feature** — not the core offering

Goal: Both tiers in one app, one universe.json, one scheduler codebase, but with **tiered update frequencies** so we don't overload API/CPU.

## Technical Implementation Plan (agreed)
- Single source of truth: `universe.json`
- Add one new field to every asset:
  - `"update_frequency": "real_time"` // or `"daily"` or `"weekly"`
- Default for new symbols: `"none"` or missing → no scheduling
- Scheduler behavior:
  - High-frequency scheduler (every 15 min): process only `"real_time"` symbols (~100 max)
  - Daily/weekly scheduler: process `"daily"` + `"weekly"` symbols (~1500)
- No separate universes or duplicate lists — everything lives in one JSON file
- Flags are **permanent** (production control mechanism), not temporary
  - `"real_time"` = always on for core symbols
  - `"daily"` or `"weekly"` = batch updates for earnings tier
  - Manual edits / future admin UI will change these flags

## Immediate Next Step (this commit only)
- Add the field `"update_frequency"` to the schema in universe.json
- Set initial values:
  - For current core symbols (SPY, AAPL, BTCUSD, etc.): `"real_time"`
  - For all other / future 1500 earnings stocks: `"daily"`
- Update core/assets_registry.py to expose helper functions (e.g. `real_time_assets()`, `daily_assets()`)
- No changes yet to scheduler.py or backfill — only schema + initial population
- Test: load_universe() should show the new field correctly
