# Reverse-Engineer Plan: Replicate SPY Architecture for All 49 Symbols

## Backup (DONE ✅)

- **Location:** `backups/backup_20260222_005516_pre_reverse_engineer_assets/`
- **Also backed up:** `regime_cache.db`, `regime_cache_SPY_escalation_frozen_2026-02-19.db`

---

## Architecture (Current)

**Rule:** `live.db` must never contain derived tables. Only bars + fetch_cursor (+ ingestion metadata).

| DB | Contents |
|----|----------|
| **live.db** | bars, fetch_cursor (ingestion only) |
| **frozen_YYYY-MM-DD.db** | bars only (raw input snapshot for reproducibility) |
| **compute.db** | escalation_history_v3, state_history, latest_state (derived outputs) |

Compute reads frozen, writes compute.db. Never reads or writes live.db for derived data.

---

## Pipeline

**Order:** ingest → validate → freeze (bars only) → compute → verify

| Step | Script | Action |
|------|--------|--------|
| 1. Ingest | `backfill_asset_full.py` | Download bars → live.db |
| 2. Validate | `validate_asset_bars.py` | Check bars exist, sufficient count |
| 3. Freeze | `freeze_asset_db.py` | live.db bars → frozen_YYYY-MM-DD.db (bars only) |
| 4. Compute | `compute_asset_full.py` | Read frozen → write escalation + state → compute.db |
| 5. Verify | `validation_leadtime_spy.py` (SPY) | Optional |

**Orchestrator:** `pipeline_asset_full.py` runs steps 1–4 (or 2–4 with `--skip-ingest` if bars already in live.db).

---

## Scripts

| Script | Purpose |
|--------|---------|
| `backfill_asset_full.py` | Ingest bars from Twelve Data → live.db |
| `validate_asset_bars.py` | Validate bars before freeze |
| `freeze_asset_db.py` | Freeze bars-only snapshot → frozen_YYYY-MM-DD.db |
| `compute_asset_full.py` | Read frozen bars → write escalation_history_v3, state_history, latest_state → compute.db |
| `pipeline_asset_full.py` | Run full pipeline (ingest → validate → freeze → compute) |

---

## Local Test

```bash
# Full pipeline (includes ingest)
python3 scripts/pipeline_asset_full.py --symbol QQQ

# Skip ingest if bars already in live.db
python3 scripts/pipeline_asset_full.py --symbol QQQ --skip-ingest

# Single timeframe (faster)
python3 scripts/pipeline_asset_full.py --symbol QQQ -t 1day --skip-ingest

# Verify compute.db
sqlite3 data/assets/QQQ/compute.db "SELECT 'esc_v3', COUNT(*) FROM escalation_history_v3 UNION ALL SELECT 'latest', COUNT(*) FROM latest_state UNION ALL SELECT 'state_hist', COUNT(*) FROM state_history;"
```

---

## Vultr Deployment (Batch Run)

1. **Provision** a Vultr CPU instance (e.g. 4 vCPU, 8GB RAM).
2. **Clone** the repo and install deps: `pip install -e .` (or `pip install pandas numpy`).
3. **Upload** `data/assets/` so each symbol has `live.db` with bars.
4. **Run** per symbol (or loop):

```bash
for sym in QQQ DIA IWM EFA EEM EWJ EZU EWZ EWA FXI AAPL MSFT NVDA AMZN META GOOGL TSLA EURUSD GBPUSD USDJPY AUDUSD USDCAD BTCUSD BNBUSD ETHUSD SOLUSD XRPUSD LINKUSD XAUUSD XAGUSD XPTUSD CLUSD XBRUSD NGUSD HGUSD ZCUSD TLT IEF BND EMB LQD HYG US10Y US30Y IGOV VNQ VNQI; do
  echo "=== $sym ==="
  python3 scripts/pipeline_asset_full.py --symbol $sym --skip-ingest
done
```

5. **Download** `data/assets/*/frozen_*.db` and `data/assets/*/compute.db` back to your machine.

---

## Risks & Safeguards

- **Backup exists** – can restore from `backups/`
- **Test on 1 symbol first** – e.g. QQQ, before batch run
- **Compute time** – full history with expanding window is slow; use `-t 1day` for quick tests, run overnight for all TFs
