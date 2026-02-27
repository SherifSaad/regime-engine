#!/usr/bin/env python3
"""
Real-time monitor for vultr_run_compute. Run in a separate terminal.

Usage:
  python scripts/vultr_monitor.py
  python scripts/vultr_monitor.py --interval 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "vultr_run_state.json"
RUNNING_FILE = PROJECT_ROOT / "vultr_running.json"


def main() -> None:
    ap = argparse.ArgumentParser(description="Monitor Vultr compute progress")
    ap.add_argument("--interval", type=int, default=3, help="Refresh interval (seconds)")
    args = ap.parse_args()

    total = 1565
    last_n = 0
    last_t = time.time()

    try:
        while True:
            if not STATE_FILE.exists():
                print("\rWaiting for vultr_run_state.json...", end="", flush=True)
                time.sleep(args.interval)
                continue

            with open(STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)

            completed = state.get("completed", [])
            failed = state.get("failed", {})
            n_completed = len(completed)
            n_failed = len(failed)
            n_pending = total - n_completed - n_failed

            # Rate (symbols/min) from last interval
            rate = (n_completed - last_n) / (args.interval / 60) if last_n > 0 or n_completed > 0 else 0
            last_n = n_completed

            if n_pending > 0 and rate > 0:
                eta_str = f"ETA ~{n_pending / rate:.0f} min"
            elif rate > 0:
                eta_str = f"Rate: {rate:.1f}/min"
            else:
                eta_str = ""

            # Load running workers (which symbols are being computed now)
            running = {}
            if RUNNING_FILE.exists():
                try:
                    with open(RUNNING_FILE, encoding="utf-8") as f:
                        running = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

            # Clear screen and home cursor
            print("\033[2J\033[H", end="")
            print("=== Vultr compute progress (Ctrl+C to exit) ===\n")
            print(f"  Completed: {n_completed}/{total}")
            print(f"  Failed:    {n_failed}")
            print(f"  Pending:   {n_pending}")
            print(f"  {eta_str}")
            if running:
                workers = [f"W{i}:{s}" for i, s in sorted(running.items(), key=lambda x: int(x[0]))]
                print(f"\n  Workers computing now ({len(running)}):")
                print(f"  {', '.join(workers)}")
            if completed:
                print(f"\n  Last done: {', '.join(completed[-5:])}")
            if failed:
                print(f"  Last failed: {', '.join(list(failed.keys())[-3:])}")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
