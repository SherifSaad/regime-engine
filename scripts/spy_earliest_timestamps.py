#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
if not API_KEY:
    raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")

SYMBOL = "SPY"
INTERVALS = ["15min", "1h", "4h", "1day", "1week"]

URL = "https://api.twelvedata.com/earliest_timestamp"

def earliest(symbol: str, interval: str) -> str:
    params = {"apikey": API_KEY, "symbol": symbol, "interval": interval, "format": "JSON"}
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"{interval}: {data.get('message')}")
    # Typical response contains a timestamp field; print raw if unsure
    # Many Twelve Data endpoints use 'datetime' keys; we defensively handle a few.
    for k in ("datetime", "timestamp", "earliest_timestamp", "date", "value"):
        if k in data:
            return str(data[k])
    return str(data)

if __name__ == "__main__":
    print(f"SYMBOL: {SYMBOL}")
    for iv in INTERVALS:
        ts = earliest(SYMBOL, iv)
        print(f"{iv:6s} -> {ts}")
