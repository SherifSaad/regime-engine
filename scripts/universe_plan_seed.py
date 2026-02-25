from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = REPO_ROOT / "data" / "index"

UNIVERSE_TXT = REPO_ROOT / "universe_symbols.txt"
PLAN_JSON = INDEX_DIR / "universe_plan.json"

BATCH_SIZE_DEFAULT = 50


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_symbols(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    symbols: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        # normalize to uppercase, keep dots/hyphens as-is (BRK.B, RDS-A etc.)
        symbols.append(s.upper())

    # de-dup while preserving order
    seen = set()
    uniq: list[str] = []
    for s in symbols:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def load_plan(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Create it first (universe_plan.json).")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_plan_shape(plan: dict) -> dict:
    # Minimal shape validation + defaults (no hardcoding of symbol counts)
    plan.setdefault("generated_utc", None)
    plan.setdefault("batch_size", BATCH_SIZE_DEFAULT)
    plan.setdefault("phases", [])
    plan.setdefault("batches", [])
    plan.setdefault("symbols", [])
    return plan


def seed_universe(plan: dict, symbols: list[str]) -> dict:
    batch_size = int(plan.get("batch_size") or BATCH_SIZE_DEFAULT)

    # PHASE U is your Universe Build (D1/W1). Ensure it exists.
    phases = {p.get("phase_id"): p for p in plan.get("phases", []) if isinstance(p, dict)}
    if "U" not in phases:
        plan["phases"] = plan.get("phases", []) + [
            {
                "phase_id": "U",
                "name": "Universe Build (D1/W1 only)",
                "timeframes": ["1day", "1week"],
                "notes": "Download full history, freeze, compute D1/W1, verify, wire to app. Intraday added later.",
            }
        ]

    # Create batches U001.. based on symbol count
    batches = []
    for i in range(0, len(symbols), batch_size):
        batch_num = (i // batch_size) + 1
        batch_id = f"U{batch_num:03d}"
        chunk = symbols[i : i + batch_size]
        batches.append(
            {
                "batch_id": batch_id,
                "phase_id": "U",
                "symbols": chunk,
                "status": "TODO",  # TODO | IN_PROGRESS | DONE
                "notes": "",
                "created_utc": utc_now_iso(),
                "updated_utc": utc_now_iso(),
            }
        )

    # Per-symbol tracking rows (progress flags)
    sym_rows = []
    for s in symbols:
        sym_rows.append(
            {
                "symbol": s,
                "phase_id": "U",
                "batch_id": None,  # filled below
                "ingested": "TODO",
                "frozen_db": "TODO",
                "computed_d1w1": "TODO",
                "verified": "TODO",
                "wired_to_app": "TODO",
                "eras_applied": "TODO",
                "aggressive_validation": "TODO",
                "notes": "",
                "last_checked_utc": None,
            }
        )

    # Fill batch_id for each symbol row
    batch_map = {}
    for b in batches:
        for s in b["symbols"]:
            batch_map[s] = b["batch_id"]
    for r in sym_rows:
        r["batch_id"] = batch_map.get(r["symbol"])

    plan["generated_utc"] = utc_now_iso()
    plan["batches"] = batches
    plan["symbols"] = sym_rows
    return plan


def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    symbols = read_symbols(UNIVERSE_TXT)
    if not symbols:
        raise RuntimeError("universe_symbols.txt is empty after cleaning.")

    plan = ensure_plan_shape(load_plan(PLAN_JSON))
    plan = seed_universe(plan, symbols)

    PLAN_JSON.write_text(json.dumps(plan, indent=2, sort_keys=False), encoding="utf-8")

    total = len(symbols)
    batches = len(plan["batches"])
    bs = plan["batch_size"]
    print(f"[OK] Seeded universe_plan.json")
    print(f"     Symbols: {total}")
    print(f"     Batch size: {bs}")
    print(f"     Batches: {batches}")
    print(f"     First batch: {plan['batches'][0]['batch_id']} ({len(plan['batches'][0]['symbols'])} symbols)")
    print(f"     Last batch : {plan['batches'][-1]['batch_id']} ({len(plan['batches'][-1]['symbols'])} symbols)")


if __name__ == "__main__":
    main()
