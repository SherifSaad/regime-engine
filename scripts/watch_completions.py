#!/usr/bin/env python3
"""
Watch vultr_run_state.json and append each new completion to completions.log.
Run in background, then: tail -f ~/regime-engine/completions.log
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "vultr_run_state.json"
LOG = ROOT / "completions.log"

# Create log file immediately so tail -f works
try:
    LOG.touch()
except OSError as e:
    print(f"watch_completions: cannot create {LOG}: {e}", file=__import__("sys").stderr)
    raise SystemExit(1)

seen = set()
while True:
    try:
        if STATE.exists():
            with open(STATE) as f:
                d = json.load(f)
            for s in d.get("completed", []):
                if s not in seen:
                    seen.add(s)
                    with open(LOG, "a") as out:
                        out.write(f"{s} done\n")
                        out.flush()
    except Exception:
        pass
    time.sleep(5)
