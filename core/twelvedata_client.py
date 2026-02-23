# core/twelvedata_client.py
from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()
import time
from typing import Any, Dict, Optional
import requests


BASE_URL = "https://api.twelvedata.com"


def get_api_key() -> str:
    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing TWELVEDATA_API_KEY env var.")
    return key


def _request(path: str, params: Dict[str, Any], timeout: int = 20) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data


def ping() -> str:
    """
    Cheap call: just checks the key is accepted.
    Twelve Data has multiple endpoints; /api_usage is useful for validation.
    """
    key = get_api_key()
    data = _request("/api_usage", {"apikey": key})
    if "message" in data and "error" in str(data.get("message", "")).lower():
        raise RuntimeError(f"TwelveData error: {data}")
    return "ok"


def time_series(
    symbol: str,
    interval: str,
    outputsize: int = 5000,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    key = get_api_key()
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "timezone": timezone,
        "apikey": key,
        "format": "JSON",
    }
    return _request("/time_series", params)


def quote(symbol: str) -> Dict[str, Any]:
    key = get_api_key()
    return _request("/quote", {"symbol": symbol, "apikey": key})
