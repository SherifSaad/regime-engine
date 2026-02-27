#!/usr/bin/env python3
"""
Vultr batch compute: run compute_asset_full for all symbols with Parquet bars.
Resumable, parallel, tracks progress.

Usage (on Vultr):
  pip install regime-engine[perf]   # Numba speedup
  python scripts/vultr_run_compute.py --workers 4
  python scripts/vultr_run_compute.py --workers 4 --resume
  python scripts/vultr_run_compute.py --status

Progress: vultr_run_state.json (completed, failed, timings)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "vultr_run_state.json"
RUNNING_FILE = PROJECT_ROOT / "vultr_running.json"
COMPUTE_SCRIPT = Path(__file__).resolve().parent / "compute_asset_full.py"

RUNNING_SLOTS: list[str | None] = []
RUNNING_LOCK = threading.Lock()


def get_symbols_with_bars() -> list[str]:
    """Symbols that have Parquet bars (any timeframe)."""
    assets = PROJECT_ROOT / "data" / "assets"
    if not assets.exists():
        return []
    symbols = []
    for d in sorted(assets.iterdir()):
        if not d.is_dir():
            continue
        bars = d / "bars"
        if bars.exists() and any(bars.iterdir()):
            symbols.append(d.name)
    return symbols


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "failed": {}, "started_at": None, "updated_at": None}


def save_state(state: dict) -> None:
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _write_running() -> None:
    d = {str(i): s for i, s in enumerate(RUNNING_SLOTS) if s}
    with open(RUNNING_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f)


def run_compute(symbol: str) -> tuple[str, bool, float, str]:
    """Run compute_asset_full for one symbol. Returns (symbol, ok, duration, error)."""
    slot = -1
    if RUNNING_SLOTS:
        with RUNNING_LOCK:
            for i in range(len(RUNNING_SLOTS)):
                if RUNNING_SLOTS[i] is None:
                    RUNNING_SLOTS[i] = symbol
                    slot = i
                    break
        if slot >= 0:
            _write_running()

    t0 = time.perf_counter()
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    try:
        r = subprocess.run(
            [sys.executable, str(COMPUTE_SCRIPT), "--symbol", symbol, "--input", "parquet"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        duration = time.perf_counter() - t0
        if r.returncode == 0:
            return symbol, True, duration, ""
        return symbol, False, duration, (r.stderr or r.stdout or "unknown")[:500]
    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - t0
        return symbol, False, duration, "timeout"
    except Exception as e:
        duration = time.perf_counter() - t0
        return symbol, False, duration, str(e)[:500]
    finally:
        if slot >= 0 and RUNNING_SLOTS:
            with RUNNING_LOCK:
                RUNNING_SLOTS[slot] = None
            _write_running()


def main() -> None:
    ap = argparse.ArgumentParser(description="Vultr: run compute for all symbols with Parquet")
    ap.add_argument("--workers", type=int, default=4, help="Parallel workers")
    ap.add_argument("--resume", action="store_true", help="Skip already completed")
    ap.add_argument("--status", action="store_true", help="Show progress only")
    ap.add_argument("--limit", type=int, help="Max symbols to run (for testing)")
    args = ap.parse_args()

    symbols = get_symbols_with_bars()
    if not symbols:
        print("No symbols with Parquet bars found in data/assets/")
        sys.exit(1)

    state = load_state()
    completed_set = set(state.get("completed", []))
    failed_dict = state.get("failed", {})

    if args.status:
        pending = [s for s in symbols if s not in completed_set and s not in failed_dict]
        print(f"Total symbols with bars: {len(symbols)}")
        print(f"Completed: {len(completed_set)}")
        print(f"Failed: {len(failed_dict)}")
        print(f"Pending: {len(pending)}")
        if failed_dict:
            print("\nLast 5 failed:")
            for s, err in list(failed_dict.items())[-5:]:
                print(f"  {s}: {err[:80]}...")
        return

    to_run = [s for s in symbols if s not in completed_set]
    if args.resume:
        to_run = [s for s in to_run if s not in failed_dict]
    else:
        failed_dict = {}
        state["failed"] = {}

    if args.limit:
        to_run = to_run[: args.limit]

    if not to_run:
        print("Nothing to run. All done or use --resume to retry failed.")
        return

    if not state.get("started_at"):
        state["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    state["completed"] = list(completed_set)
    state["failed"] = failed_dict
    save_state(state)

    print(f"Running compute for {len(to_run)} symbols ({args.workers} workers)")
    print(f"Progress: {STATE_FILE}")
    print(f"Running: {RUNNING_FILE}")
    print()

    global RUNNING_SLOTS
    RUNNING_SLOTS = [None] * args.workers
    if RUNNING_FILE.exists():
        RUNNING_FILE.unlink()

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_compute, s): s for s in to_run}
        for fut in as_completed(futures):
            symbol, ok, duration, err = fut.result()
            done += 1
            if ok:
                state["completed"].append(symbol)
                print(f"[{done}/{len(to_run)}] {symbol} OK ({duration:.1f}s)")
            else:
                state["failed"][symbol] = err
                print(f"[{done}/{len(to_run)}] {symbol} FAIL ({duration:.1f}s): {err[:60]}...")
            save_state(state)  # save every symbol so monitor sees real-time progress

    save_state(state)
    RUNNING_SLOTS.clear()
    if RUNNING_FILE.exists():
        RUNNING_FILE.unlink()
    print(f"\nDone. Completed: {len(state['completed'])}, Failed: {len(state['failed'])}")


if __name__ == "__main__":
    main()
