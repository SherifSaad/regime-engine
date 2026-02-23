from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- Paths (no hardcoding of assets/classes) ---
REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = REPO_ROOT / "data" / "index"

REGISTRY_PATH = INDEX_DIR / "registry.json"
STATS_PATH = INDEX_DIR / "stats.json"

app = FastAPI(title="Regime Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"{path.name} not found")
    return json.loads(path.read_text())


# -------------------------
# Core Endpoints
# -------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def get_stats():
    """
    Landing page dynamic stats.
    No hardcoded numbers.
    """
    return load_json(STATS_PATH)


@app.get("/asset-classes")
def get_asset_classes():
    registry = load_json(REGISTRY_PATH)
    return registry.get("asset_classes", [])


@app.get("/timeframes")
def get_timeframes():
    registry = load_json(REGISTRY_PATH)
    return registry.get("timeframes", [])


@app.get("/assets")
def get_assets(asset_class: str | None = None):
    """
    Returns all assets or filtered by asset_class.
    """
    registry = load_json(REGISTRY_PATH)
    assets = registry.get("assets", [])

    if asset_class:
        assets = [a for a in assets if a.get("asset_class") == asset_class]

    return assets


@app.get("/asset/{symbol}")
def get_asset(symbol: str):
    registry = load_json(REGISTRY_PATH)
    assets = registry.get("assets", [])
    for asset in assets:
        if asset.get("symbol") == symbol:
            return asset

    raise HTTPException(status_code=404, detail="Asset not found")
