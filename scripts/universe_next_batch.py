from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_JSON = REPO_ROOT / "data" / "index" / "universe_plan.json"


def load_plan() -> dict:
    if not PLAN_JSON.exists():
        raise FileNotFoundError(f"Missing {PLAN_JSON}")
    return json.loads(PLAN_JSON.read_text(encoding="utf-8"))


def main():
    plan = load_plan()
    batches = plan.get("batches", [])
    if not batches:
        raise RuntimeError("No batches in universe_plan.json")

    # Pick first batch with status != DONE
    for b in batches:
        status = (b.get("status") or "TODO").upper()
        if status != "DONE":
            batch_id = b["batch_id"]
            symbols = b.get("symbols", [])
            print(batch_id)
            print(" ".join(symbols))
            return

    print("ALL_DONE")


if __name__ == "__main__":
    main()
