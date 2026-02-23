# Reverse-Engineer Plan: Replicate SPY Architecture for All 49 Symbols

## Backup (DONE ✅)

- **Location:** `backups/backup_20260222_005516_pre_reverse_engineer_assets/`
- **Also backed up:** `regime_cache.db`, `regime_cache_SPY_escalation_frozen_2026-02-19.db`

---

## Current State

| Asset | bars | fetch_cursor | escalation_history_v3 | latest_state | state_history |
|-------|------|--------------|------------------------|--------------|---------------|
| **SPY** | ✅ 62,756 | ✅ | ✅ 62,601 | ✅ 5 | ✅ 405 |
| **Others (49)** | ✅ | ✅ | ❌ | ❌ | ❌ |

Other symbols have only `bars` + `fetch_cursor` (from `backfill_asset_full.py`).

---

## Target (per SPY DB Final Review)

Each `data/assets/<SYMBOL>/` should have:

- **live.db** with: bars, fetch_cursor, escalation_history_v3, latest_state, state_history
- **frozen_YYYY-MM-DD.db** (immutable copy of live.db for validation)
- **inventory.json** (coverage per TF)

---

## Pipeline to Build

### Step 1: Extend live.db schema (for symbols that only have bars)

Add tables if missing: `escalation_history_v3`, `latest_state`, `state_history`.

### Step 2: Compute script (no bar caps)

**Script:** `scripts/compute_asset_states_full.py` (new)

- Read bars from `data/assets/<SYMBOL>/live.db` (all bars, no LIMIT)
- For each timeframe:
  - For each bar `i`: use expanding window `df[:i+1]`, call `compute_market_state_from_df`
  - Write to `latest_state` (upsert) and `state_history` (insert)
- Ensure schema exists before writing

### Step 3: Escalation backfill (escalation_history_v3)

**Script:** `scripts/backfill_escalation_v3.py` (new, based on `backfill_spy_signals_1day.py`)

- Read bars from live.db (all bars, no LIMIT)
- Compute esc_raw, esc_pctl, esc_bucket via `compute_escalation_v2_series` + `rolling_percentile_transform`
- Write to `escalation_history_v3` table
- Create table if not exists

### Step 4: Freeze script

**Script:** `scripts/freeze_asset_db.py` (new)

- Copy `live.db` → `frozen_YYYY-MM-DD.db`
- Idempotent (skip if frozen already exists for today)

### Step 5: Orchestrator (optional)

**Script:** `scripts/pipeline_asset_full.py`

- For a given symbol: ensure schema → compute states → backfill escalation → freeze
- Or run each step manually per symbol

---

## Execution Order (per symbol)

1. `backfill_asset_full.py --symbol X` (already done for most – ensures bars + fetch_cursor)
2. `compute_asset_states_full.py --symbol X` (new)
3. `backfill_escalation_v3.py --symbol X` (new)
4. `freeze_asset_db.py --symbol X` (new)

---

## Risks & Safeguards

- **Backup exists** – can restore from `backups/`
- **SPY untouched** – scripts will skip or no-op if data already present (resumable)
- **Test on 1 symbol first** – e.g. QQQ, before batch run
- **Compute time** – full history with expanding window is slow; consider sampling for intraday (e.g. every 4th bar for 15m) or run overnight

---

## Scripts Implemented ✅

1. `scripts/compute_asset_states_full.py` – full data, expanding window, writes latest_state + state_history
2. `scripts/backfill_escalation_v3.py` – esc_raw, esc_pctl, esc_bucket → escalation_history_v3
3. `scripts/freeze_asset_db.py` – copies live.db → frozen_YYYY-MM-DD.db

---

## Local Test (QQQ)

```bash
# 1. Compute states (1day only for quick test; use --all for full)
python3 scripts/compute_asset_states_full.py --symbol QQQ -t 1day

# 2. Backfill escalation v3
python3 scripts/backfill_escalation_v3.py --symbol QQQ

# 3. Freeze
python3 scripts/freeze_asset_db.py --symbol QQQ

# Verify
sqlite3 data/assets/QQQ/live.db "SELECT 'bars', COUNT(*) FROM bars UNION ALL SELECT 'esc_v3', COUNT(*) FROM escalation_history_v3 UNION ALL SELECT 'latest', COUNT(*) FROM latest_state UNION ALL SELECT 'state_hist', COUNT(*) FROM state_history;"
```

---

## Vultr Deployment (Batch Run)

1. **Provision** a Vultr CPU instance (e.g. 4 vCPU, 8GB RAM).
2. **Clone** the repo and install deps: `pip install -e .` (or `pip install pandas numpy`).
3. **Upload** `data/assets/` (or sync from your machine) so each symbol has `live.db` with bars.
4. **Run** per symbol (or loop):

```bash
for sym in QQQ DIA IWM EFA EEM EWJ EZU EWZ EWA FXI AAPL MSFT NVDA AMZN META GOOGL TSLA EURUSD GBPUSD USDJPY AUDUSD USDCAD BTCUSD BNBUSD ETHUSD SOLUSD XRPUSD LINKUSD XAUUSD XAGUSD XPTUSD CLUSD XBRUSD NGUSD HGUSD ZCUSD TLT IEF BND EMB LQD HYG US10Y US30Y IGOV VNQ VNQI; do
  echo "=== $sym ==="
  python3 scripts/compute_asset_states_full.py --symbol $sym
  python3 scripts/backfill_escalation_v3.py --symbol $sym
  python3 scripts/freeze_asset_db.py --symbol $sym
done
```

5. **Download** `data/assets/*/frozen_*.db` and `live.db` back to your machine.
