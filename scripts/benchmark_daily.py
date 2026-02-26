#!/usr/bin/env python3
"""
Benchmark daily symbols pipeline: backfill (1day+1week) → validate → compute.

Times the full A-to-Z flow for daily assets. Use --skip-ingest to skip backfill
when Parquet data already exists (measures validate + compute only).

Usage:
  python scripts/benchmark_daily.py                    # One symbol (first daily)
  python scripts/benchmark_daily.py --symbol GOOG     # Specific symbol
  python scripts/benchmark_daily.py --limit 3         # First 3 daily symbols
  python scripts/benchmark_daily.py --skip-ingest     # Skip backfill (data exists)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from core.assets_registry import daily_assets

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], label: str) -> tuple[bool, float]:
    """Run command, return (success, seconds)."""
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600)
    elapsed = time.perf_counter() - t0
    if r.returncode != 0:
        print(f"  [{label}] FAILED ({elapsed:.2f}s): {r.stderr[:300]}", file=sys.stderr)
        return False, elapsed
    return True, elapsed


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark daily pipeline (1day+1week) A-to-Z")
    ap.add_argument("--symbol", help="Single symbol (e.g. GOOG). Default: first daily")
    ap.add_argument("--limit", type=int, default=1, help="Max symbols to run (default 1)")
    ap.add_argument("--skip-ingest", action="store_true", help="Skip backfill (Parquet exists)")
    args = ap.parse_args()

    daily = daily_assets()
    if not daily:
        print("No daily symbols in universe.json")
        sys.exit(1)

    if args.symbol:
        sym = args.symbol.strip().upper()
        matches = [a for a in daily if a["symbol"] == sym]
        if not matches:
            print(f"Symbol {sym} not in daily_assets()")
            sys.exit(1)
        symbols = [sym]
    else:
        symbols = [a["symbol"] for a in daily[: args.limit]]

    print(f"Benchmark: {len(symbols)} daily symbol(s) – 1day + 1week only")
    print(f"  skip-ingest={args.skip_ingest}")
    print()

    total_t0 = time.perf_counter()
    results: list[dict] = []

    for symbol in symbols:
        print(f"--- {symbol} ---")
        times: dict[str, float] = {}

        if not args.skip_ingest:
            ok, t = run(
                ["python3", "scripts/backfill_asset_partial.py", "--symbol", symbol, "--output", "parquet"],
                "backfill",
            )
            times["backfill"] = t
            if not ok:
                results.append({"symbol": symbol, "ok": False, "times": times})
                continue

        ok, t = run(
            ["python3", "scripts/validate_asset_bars.py", "--symbol", symbol, "--input", "parquet"],
            "validate",
        )
        times["validate"] = t
        if not ok:
            results.append({"symbol": symbol, "ok": False, "times": times})
            continue

        ok, t = run(
            ["python3", "scripts/compute_asset_full.py", "--symbol", symbol, "--input", "parquet"],
            "compute",
        )
        times["compute"] = t
        results.append({"symbol": symbol, "ok": ok, "times": times})

        for step, sec in times.items():
            print(f"  {step}: {sec:.2f}s")
        print()

    total_elapsed = time.perf_counter() - total_t0

    # Summary
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for r in results:
        status = "OK" if r["ok"] else "FAILED"
        parts = [f"{k}={v:.2f}s" for k, v in r["times"].items()]
        print(f"  {r['symbol']}: {status}  {'  '.join(parts)}")
    print(f"\nTotal wall time: {total_elapsed:.2f}s")
    print(f"Symbols: {len([r for r in results if r['ok']])}/{len(results)} succeeded")

    if any(not r["ok"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
