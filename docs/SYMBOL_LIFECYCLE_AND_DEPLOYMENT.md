# Symbol Lifecycle & Deployment — Who Does What

**Purpose:** Clarify what you do vs what the system does for each symbol state. Use before Vultr deployment and when adding new symbols.

---

## 1. Brand New Symbol

**You do:**
- Add the symbol to `universe.json` with:
  - `symbol`, `provider_symbol` (e.g. `"BTC/USD"` for crypto)
  - `asset_class`, `update_frequency` (`"15min"` = core, `"daily"` = daily)
  - `scheduler_enabled: true`, `active: true`
  - `tags: ["core"]` if core, or no core tag if daily

**System does:** Nothing until you run backfill or pipeline. The symbol is now in the universe and will be picked up by schedulers and backfill scripts.

---

## 2. Symbol with No Parquet Yet — Need Historical Data from Twelve Data

### 2a. Daily Symbol (1day + 1week only)

**You do:**
```bash
python scripts/pipeline_asset_full.py --symbol SYMBOL --mode daily
```
Or step by step:
```bash
python scripts/backfill_asset_partial.py --symbol SYMBOL --output parquet
python scripts/validate_asset_bars.py --symbol SYMBOL --input parquet
python scripts/compute_asset_full.py --symbol SYMBOL --input parquet
```

**System does:**
- `backfill_asset_partial`: Fetches 1day + 1week bars from Twelve Data (full history, paged) → writes to `data/assets/SYMBOL/bars/{1day,1week}/`
- `validate`: Checks bars (no duplicates, OHLC sanity)
- `compute_asset_full`: Escalation + state → `data/assets/SYMBOL/compute.db`

### 2b. Core Symbol (all 5 timeframes)

**You do:**
```bash
python scripts/pipeline_asset_full.py --symbol SYMBOL --mode core
```
Or step by step:
```bash
python scripts/backfill_asset_full.py --symbol SYMBOL --output parquet
python scripts/validate_asset_bars.py --symbol SYMBOL --input parquet
python scripts/compute_asset_full.py --symbol SYMBOL --input parquet
```

**System does:**
- `backfill_asset_full`: Fetches 15min, 1h, 4h, 1day, 1week from Twelve Data → Parquet
- Same validate + compute as above

**Requires:** `TWELVEDATA_API_KEY` in `.env`

---

## 3. Symbol with Parquet Already (Bars Exist)

**You do:** Nothing for bars. Parquet is the canonical storage. If `data/assets/SYMBOL/bars/` exists with 1day/1week (daily) or all 5 TFs (core), bars are done.

**System does:** Nothing automatically. You run compute when needed.

---

## 4. Symbol That Only Needs Calculations (Parquet Exists, No New Bars)

**You do:**
```bash
python scripts/pipeline_asset_full.py --symbol SYMBOL --mode daily --skip-ingest
# or for core:
python scripts/pipeline_asset_full.py --symbol SYMBOL --mode core --skip-ingest
```

Or compute only (no validate):
```bash
python scripts/compute_asset_full.py --symbol SYMBOL --input parquet
```

**System does:**
- Skips backfill (no API calls)
- Validates Parquet (if not --skip-ingest)
- Runs compute_asset_full → writes `compute.db`

**Use case:** You copied Parquet from elsewhere, or you're re-running compute after code/param changes (`--force-recompute` equivalent).

---

## 5. After All Full Calculations Done — Ready for UI & Deploy

**State:** Every symbol has:
- `data/assets/{symbol}/bars/{tf}/` — Parquet bars
- `data/assets/{symbol}/compute.db` — escalation_history_v3, state_history, latest_state

**You do:** Build and deploy the UI. UI reads from `compute.db` (latest_state, state_history).

**System does:** Nothing. One-time backfill + compute is complete.

---

## 6. Ongoing Operation — Schedulers Take Over

Once deployed, **scheduler_core** and **scheduler_daily** handle everything:

| Scheduler | Assets | Timeframes | When | What it does |
|-----------|--------|------------|------|---------------|
| **scheduler_core** | core_assets() | 15min, 1h, 4h, 1day, 1week | Every 15 min | Fetch incremental bars → append Parquet → run compute_asset_full when new bars |
| **scheduler_daily** | daily_assets() | 1day, 1week | Once/day (e.g. 16:01 EST) | Fetch 1day+1week → append Parquet → run compute_asset_full when new bars |

**You do:** Run the scheduler (cron or manually). Ensure `TWELVEDATA_API_KEY` in `.env`.

**System does:**
- Fetch new bars from Twelve Data (incremental, from last ts in Parquet)
- Append to Parquet via BarsProvider
- If `inserted > 0` (or `--force-recompute`): run `compute_asset_full` → update compute.db
- If no new bars: skip compute (saves time)

---

## 7. Summary Table

| Scenario | You do | System does |
|----------|--------|-------------|
| **New symbol** | Add to universe.json | — |
| **Daily, no bars** | `pipeline_asset_full --symbol X --mode daily` | Backfill 1d+1w → validate → compute |
| **Core, no bars** | `pipeline_asset_full --symbol X --mode core` | Backfill 5 TFs → validate → compute |
| **Parquet exists** | — | Bars done |
| **Compute only** | `pipeline_asset_full --skip-ingest` or `compute_asset_full` | Validate + compute (no fetch) |
| **All done** | Deploy UI | — |
| **Ongoing** | Run schedulers (cron) | Fetch → Parquet → compute when new bars |

---

## 8. Vultr One-Time Run (Before UI Deploy)

**Goal:** Get all symbols to "full calculations done" on a fast server.

1. **Copy project + .env** (with TWELVEDATA_API_KEY) to Vultr
2. **For symbols with no Parquet:** Run backfill (batch or one-by-one)
3. **For symbols with Parquet:** Run compute only (`--skip-ingest` or `compute_asset_full`)
4. **Copy back:** `data/assets/*/compute.db` (and Parquet if you backfilled there)
5. **Destroy** Vultr instance

**Batch option:** `pipeline_batch_full.py --batch-file batches/U001.txt --mode daily` (if batch files exist)
