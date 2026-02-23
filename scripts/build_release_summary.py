import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VO = ROOT / "validation_outputs"


ASSETS = ["SPY", "QQQ", "NVDA", "BTCUSD", "XAUUSD"]


def main():
    p = argparse.ArgumentParser(description="Build cross-asset release summary CSV from release audit bundles")
    p.add_argument("--date", required=True, help="YYYYMMDD (e.g., 20260217)")
    p.add_argument("--version", default="v1", help="v1, v2, ...")
    args = p.parse_args()

    rows = []
    for sym in ASSETS:
        bundle_dir = VO / sym / f"release-audit-{args.date}-{args.version}"
        latest_path = bundle_dir / "latest_state.json"
        meta_path = bundle_dir / "metadata.json"

        if not latest_path.exists() or not meta_path.exists():
            raise SystemExit(f"Missing bundle files for {sym}: {bundle_dir}")

        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        state = latest.get("latest_state", {})
        cls = state.get("classification", {})
        m = state.get("metrics", {})

        row = {
            "symbol": sym,
            "bundle": str(bundle_dir),
            "asof": latest.get("asof"),
            "regime": cls.get("regime_label"),
            "confidence": cls.get("confidence"),
            "conviction": next(
                (t for t in cls.get("strategy_tags", []) if str(t).endswith("_CONVICTION")),
                None,
            ),
            "escalation_v2": state.get("escalation_v2", None),
            "risk_level": m.get("risk_level", None),
            "realized_vol": m.get("realized_vol", None),
            "vrs": m.get("vrs", None),
            "iix": m.get("instability_index", None),
            "dsr": m.get("downside_shock_risk", None),
            "ss": m.get("structural_score", None),
            "mb": m.get("market_bias", None),
            "lq": m.get("lq", None),
            "data_sha256": meta.get("data_sha256"),
            "git_commit": meta.get("git_commit"),
        }
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)

    out = VO / f"release_summary_{args.date}_{args.version}.csv"
    df.to_csv(out, index=False)
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
