#!/usr/bin/env python3
"""
Run full pipeline for many symbols from a batch file.

Same flow as pipeline_asset_full.py (backfill → validate → freeze → compute),
but reads symbols from a .txt file (one symbol per line) and runs the pipeline
per symbol. Writes logs and summary to reports/batches/{batch_name}/.

Usage:
  python scripts/pipeline_batch_full.py --batch-file batches/U001.txt
  python scripts/pipeline_batch_full.py --batch-file batches/U001.txt -t 1day
  python scripts/pipeline_batch_full.py --batch-file batches/U001.txt --skip-ingest
  python scripts/pipeline_batch_full.py --batch-file batches/U001.txt --skip-if-done  # production: skip symbols already done
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _symbol_already_done(symbol: str) -> bool:
    """
    True if frozen + compute.db exist and verification passes.
    Verification: frozen has bars, compute.db has escalation_history_v3 rows.
    """
    asset_dir = PROJECT_ROOT / "data" / "assets" / symbol
    frozen_cands = sorted(asset_dir.glob("frozen_*.db"))
    if not frozen_cands:
        return False
    frozen = frozen_cands[-1]
    compute_db = asset_dir / "compute.db"
    if not compute_db.exists():
        return False
    try:
        conn_f = sqlite3.connect(str(frozen))
        bars = conn_f.execute("SELECT COUNT(*) FROM bars WHERE symbol=?", (symbol,)).fetchone()[0]
        conn_f.close()
        if bars < 100:
            return False
        conn_c = sqlite3.connect(str(compute_db))
        esc = conn_c.execute("SELECT COUNT(*) FROM escalation_history_v3 WHERE symbol=?", (symbol,)).fetchone()[0]
        conn_c.close()
        return esc > 0
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch pipeline: run pipeline_asset_full for each symbol in a batch file")
    ap.add_argument("--batch-file", required=True, help="Path to batch file, e.g. batches/U001.txt")
    ap.add_argument("-t", "--timeframe", help="Pass through to pipeline_asset_full.py (e.g. 1day)")
    ap.add_argument("--skip-ingest", action="store_true", help="Pass through to pipeline_asset_full.py")
    ap.add_argument(
        "--skip-if-done",
        action="store_true",
        help="Skip symbol if frozen + compute.db exist and verification passes (faster, production mode)",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Show pipeline output in real time (no capture). Use to debug stuck runs.",
    )
    args = ap.parse_args()

    batch_path = Path(args.batch_file)
    if not batch_path.exists():
        batch_path = PROJECT_ROOT / args.batch_file
    if not batch_path.exists():
        print(f"ERROR: Batch file not found: {args.batch_file}")
        sys.exit(1)

    # Infer batch name from filename (e.g. U001 from batches/U001.txt)
    batch_name = batch_path.stem

    # Read symbols: strip, ignore blanks, uppercase
    symbols = []
    for line in batch_path.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            symbols.append(s.upper())

    if not symbols:
        print(f"ERROR: No symbols in {batch_path}")
        sys.exit(1)

    print(f"Batch {batch_name}: {len(symbols)} symbols")

    # Output directory for this batch
    reports_dir = PROJECT_ROOT / "reports" / "batches" / batch_name
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Build pipeline command (args passed through)
    cmd_base = ["python3", "scripts/pipeline_asset_full.py"]
    tf_arg = ["-t", args.timeframe] if args.timeframe else []
    skip_arg = ["--skip-ingest"] if args.skip_ingest else []

    results = []
    n = len(symbols)
    for i, symbol in enumerate(symbols, 1):
        # Skip-if-done: skip symbol when frozen + compute.db exist and verification passes
        if args.skip_if_done and _symbol_already_done(symbol):
            print(f"[{i}/{n}] {symbol}... skip (already done)", flush=True)
            results.append({"symbol": symbol, "status": "OK", "reason": "already done (frozen + compute.db)"})
            log_path = reports_dir / f"{symbol}.log"
            log_path.write_text("Skipped: frozen + compute.db exist, verification passed\n", encoding="utf-8")
            continue

        print(f"[{i}/{n}] {symbol}...", flush=True)
        cmd = cmd_base + ["--symbol", symbol] + tf_arg + skip_arg

        # Run pipeline. --verbose: show output in real time (no capture) to debug stuck runs.
        if args.verbose:
            r = subprocess.run(cmd, cwd=PROJECT_ROOT)
            combined = ""
            log_path = reports_dir / f"{symbol}.log"
            log_path.write_text(
                f"(verbose mode: output not captured)\nreturncode={r.returncode}\n",
                encoding="utf-8",
            )
        else:
            r = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
            combined = (r.stdout or "") + "\n" + (r.stderr or "")
            log_path = reports_dir / f"{symbol}.log"
            log_path.write_text(combined, encoding="utf-8")

        # Determine status
        if r.returncode != 0:
            status = "FAIL"
            stderr_lines = (r.stderr or "").strip().splitlines()
            last_lines = stderr_lines[-2:] if len(stderr_lines) >= 2 else stderr_lines
            reason = f"returncode={r.returncode}" + (
                (" " + " | ".join(last_lines)) if last_lines else ""
            )
        elif "SKIP " in combined:
            status = "SKIP"
            reason = "ingest skipped"
            for line in combined.splitlines():
                if "SKIP " in line:
                    reason = line.strip()
                    break
        else:
            # Check if live.db was created (pipeline returned early without creating it)
            live_db = PROJECT_ROOT / "data" / "assets" / symbol / "live.db"
            if not args.skip_ingest and not live_db.exists():
                status = "SKIP"
                reason = "ingest skipped (no live.db)"
            else:
                status = "OK"
                reason = ""

        results.append({"symbol": symbol, "status": status, "reason": reason})

    # Write summary CSV
    summary_path = reports_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "status", "reason"])
        w.writeheader()
        w.writerows(results)

    # Print final counts
    ok = sum(1 for r in results if r["status"] == "OK")
    skip = sum(1 for r in results if r["status"] == "SKIP")
    fail = sum(1 for r in results if r["status"] == "FAIL")

    print(f"\n--- Batch {batch_name} ---")
    print(f"OK:   {ok}")
    print(f"SKIP: {skip}")
    print(f"FAIL: {fail}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
