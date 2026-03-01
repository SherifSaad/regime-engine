# Market Cache Service

Populates `data/market_latest.db` from Twelve Data (batch + optional WebSocket).

**Rate limits:** Twelve Data free tier ~55 credits/min. Batch uses 8 symbols/request with 12s delay. Full universe refresh takes ~30+ min; partial data appears as it arrives.

## Run

```bash
cd services/market_cache
npm install
TWELVEDATA_API_KEY=your_key node index.js
```

Or from project root:

```bash
cd services/market_cache && npm install && node index.js
```

## Env vars

- `TWELVEDATA_API_KEY` (required)
- `MARKET_CACHE_REFRESH_MINUTES` (default: 10)
- `MARKET_STREAM_MAX_SUBS` (default: 200)

## Data flow

1. **Batch refresh**: Every N minutes, fetches quotes for full universe from Twelve Data, writes to `data/market_latest.db`.
2. **WebSocket**: Reads `data/market_active_symbols.json` (updated by UI via `/api/market-subscription`), subscribes to those symbols for real-time updates.
