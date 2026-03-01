# Twelve Data Integration Plan — Per-Asset Page Enhancement

**Goal:** Elevate the per-asset page to serve both institutional and retail users. Add Twelve Data content that adds value, increases engagement, and keeps the app premium—not cheap.

---

## 1. Twelve Data Offerings by Asset Class

### Universal (all asset types)
| Endpoint | Description | Tier | Notes |
|----------|-------------|------|-------|
| `/quote` | Open, high, low, close, volume, change % | Core | Real-time / delayed |
| `/price` | Latest price only | Core | Minimal |
| `/logo` | Asset logo URL | Free | No cost; adds polish |
| `/time_series` | OHLCV history | Core | You already use this |

### Equities (US_EQUITY, US_EQUITY_INDEX)
| Endpoint | Description | Tier | Retail value |
|----------|-------------|------|--------------|
| `/profile` | Name, sector, industry, description, employees, address | Grow | Context, “who is this?” |
| `/statistics` | P/E, market cap, 52w high/low, beta, dividend yield | Pro | Quick valuation snapshot |
| `/earnings` | EPS actuals vs estimates | Grow | Earnings-aware (aligns with your regime) |
| `/earnings_calendar` | Upcoming dates | Grow | Next event |
| `/dividends` | Dividend history | Grow | Income investors |
| `/splits` | Split history | Grow | Historical context |
| `/recommendations` | Analyst buy/hold/sell | Pro | Sentiment |
| `/price_target` | Analyst price targets | Pro | Retail loves “target price” |
| `/growth_estimates` | Revenue/EPS growth | Pro | Growth narrative |
| `/balance_sheet` | Assets, liabilities | Pro | Deep dive |
| `/income_statement` | Revenue, expenses | Pro | Deep dive |
| `/cash_flow` | Cash flow | Pro | Deep dive |
| `/key_executives` | Management | Ultra+ | Optional |

### Forex (FX)
| Endpoint | Description | Tier | Retail value |
|----------|-------------|------|--------------|
| `/quote` | Bid, ask, volume | Core | Primary |
| `/profile` | Pair description | Grow | “What is EUR/USD?” |
| `/logo` | Pair logo | Free | Polish |

### Crypto (CRYPTO)
| Endpoint | Description | Tier | Retail value |
|----------|-------------|------|--------------|
| `/quote` | OHLCV | Core | Primary |
| `/profile` | Coin description | Grow | “What is BTC?” |
| `/logo` | Coin logo | Free | Polish |

### Commodities
| Endpoint | Description | Tier | Retail value |
|----------|-------------|------|--------------|
| `/quote` | Price | Core | Primary |
| `/profile` | Description | Grow | Context |
| `/logo` | Logo | Free | Polish |

### Fixed Income (Rates)
| Endpoint | Description | Tier | Notes |
|----------|-------------|------|-------|
| `/quote` | Yield | Core | If supported |
| `/fixed_income` | Bond data | Core | Dedicated endpoint |

---

## 2. What Adds Value Without Looking Cheap

### High-value, premium feel
- **Quote** — Real price, change, volume. Essential. Clean.
- **Logo** — Free, instant recognition. Feels polished.
- **Profile** — One-line description. “Apple Inc. designs consumer electronics.” Adds context.
- **Statistics** — P/E, market cap, 52w range. Dense, institutional. One compact panel.
- **Regime / Escalation** — Your core product. Keep prominent.

### Engagement drivers (retail-friendly)
- **Earnings calendar** — “Next report: Mar 15” — creates return visits.
- **Analyst recommendations** — Buy/Hold/Sell. Retail loves it.
- **Price target** — “Avg target: $195” — sticky, shareable.
- **Dividend yield** — Income investors stay.

### Avoid (cheap / cluttered)
- Too many panels in one view
- Raw financial statements (balance sheet, cash flow) as default — too heavy for casual
- Gimmicky charts or animations
- Generic “news” widgets
- Overuse of gradients, badges, or flashy UI

---

## 3. Recommended Layout by Asset Class

### Equities (US_EQUITY, US_EQUITY_INDEX)
| Section | Content | Source |
|---------|---------|--------|
| Header | Symbol, name, logo, sector | Profile, Logo |
| Quote | Price, change %, volume | Quote |
| Regime / Escalation | Your engine | compute.db |
| Snapshot | P/E, market cap, 52w high/low, div yield | Statistics |
| Earnings | Next date, last EPS vs est | Earnings, Earnings calendar |
| Analyst | Recommendations, price target | Recommendations, Price target |
| Dividends | Recent history (optional) | Dividends |

### FX
| Section | Content | Source |
|---------|---------|--------|
| Header | Symbol, name, logo | Profile, Logo |
| Quote | Price, change %, volume | Quote |
| Regime / Escalation | Your engine | compute.db |

### Crypto
| Section | Content | Source |
|---------|---------|--------|
| Header | Symbol, name, logo | Profile, Logo |
| Quote | Price, change %, volume | Quote |
| Regime / Escalation | Your engine | compute.db |

### Commodities
| Section | Content | Source |
|---------|---------|--------|
| Header | Symbol, name, logo | Profile, Logo |
| Quote | Price, change % | Quote |
| Regime / Escalation | Your engine | compute.db |

### Fixed Income
| Section | Content | Source |
|---------|---------|--------|
| Header | Symbol, name | Profile |
| Quote | Yield, change | Quote |
| Regime / Escalation | Your engine | compute.db |

---

## 4. Design Principles

1. **Regime first** — Your regime + escalation stays the hero. Twelve Data supports, not replaces.
2. **Progressive disclosure** — Summary above fold; “Details” / “Financials” expandable for deep dive.
3. **White, clean** — No gradients, no flash. Keep institutional base.
4. **Asset-appropriate** — Equities get more; FX/Crypto/Commodities stay lean.
5. **Graceful fallback** — If Twelve Data fails, show regime only. No broken placeholders.

---

## 5. Implementation Priority

| Phase | Scope | Effort |
|-------|-------|--------|
| 1 | Quote + Logo for all | Low |
| 2 | Profile (description) for all | Low |
| 3 | Statistics for equities | Low |
| 4 | Earnings + Earnings calendar for equities | Medium |
| 5 | Recommendations + Price target for equities | Medium |
| 6 | Dividends for equities (optional) | Low |

---

## 6. Symbol Mapping (Twelve Data ↔ Your Universe)

Twelve Data uses symbols like `AAPL`, `EUR/USD`, `BTC/USD`. Your universe may use `EURUSD`, `BTCUSD`. You’ll need a mapping layer for FX and Crypto.

---

## 7. API Key & Rate Limits

- `TWELVEDATA_API_KEY` already in use (scheduler, backfill).
- Free tier: 8 req/min, 800/day.
- Pro tier ($29+): higher limits for quote + fundamentals.
- Consider server-side caching (e.g. 1–5 min for quote) to reduce calls.

---

## 8. Summary

**Add:** Quote, Logo, Profile, Statistics (equities), Earnings, Recommendations, Price target.  
**Avoid:** Clutter, raw statements as default, gimmicks.  
**Keep:** Regime first, white, clean, institutional base.

This keeps the app premium while making it useful and engaging for retail.
