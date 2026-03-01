# Regime Intelligence — UI Journey & Plan

**Purpose:** A single document that explains the UI from the very beginning, where we stand now, and the plan moving forward. Use this to follow along and stay oriented.

---

## Part 1: What Was Done (History)

### 1.1 App Structure

The app is a **Next.js** project under `apps/web/`. It uses two main route groups:

| Route Group | Path | Layout | Purpose |
|-------------|------|--------|---------|
| **Public** | `(public)/` | `PublicLayout` | Marketing pages: landing, methodology, audit, pricing, login, signup, terms, privacy, FAQ, disclaimer |
| **App** | `(app)/` | `AppShell` | The actual product: overview, explorer, alerts, market-map |

**PublicLayout** = Simple header (Home, Explore, Methodology, Audit, Pricing, Login, Sign up) + footer (Disclaimer, Terms, FAQ, Privacy).

**AppShell** = Green sidebar with logo + nav (Global Overview, Asset Explorer, Alerts Center, Market Map, Audit) + top header (Home, Explorer links) + main content area.

---

### 1.2 Landing Page

- **Route:** `/` (public)
- **Content:** Hero ("See the shift before the move"), value proposition (4 pillars), how it works, coverage, trust/audit, pricing CTA
- **Primary CTA:** "Explore assets" → `/explorer`
- **Secondary:** Sign up, Log in

---

### 1.3 Asset Coverage (Now Redirected)

- **Original routes:** `/asset-coverage` and `/asset-coverage/[assetClass]`
- **What it did:** Hub of asset classes (Core Macro + Earnings). Clicking a class showed a symbol table.
- **Current state:** Both routes **redirect to `/explorer`** (or `/explorer?asset_class=X`). Coverage was merged into Explorer.

---

### 1.4 Explorer (Current Behavior — What We Have Now)

**Route:** `/explorer`

**Two modes:**

1. **Hub mode** (no `asset_class` in URL):
   - Shows asset class cards in two sections: "Core Macro" (FX, Indices, Commodities, Crypto, Rates) and "Earnings Universe" (Equities)
   - Each card links to `/explorer?asset_class=FX` (or whatever class)

2. **Drill-down mode** (`?asset_class=FX`):
   - Shows only assets in that class
   - Uses `ScreenerTable` with search, asset-class filter, pagination (25/50/100/200)
   - Table columns: Symbol, Class, Regime, Esc, Pctl, Conf, 11 metrics, Open link

**Problem with current design:** The user must first pick an asset class to see the screener. There is no single unified screener where you see **all assets** and filter by asset class (or any other criteria). Results cannot span multiple asset classes.

---

### 1.5 Asset Detail Pages

**Route:** `/explorer/[symbol]` (e.g. `/explorer/AAPL`)

- **Layout by asset class:** Equities, FX, Crypto, Commodities, Fixed Income each have their own layout component
- **Data sources:**
  - **RI API** (`riApi.asset(symbol)`): symbol, name, asset_class, has_compute
  - **Twelve Data** (`getQuoteLogoProfileStats`): quote, logo, profile, statistics, earnings, analyst
- **Components:** AssetPageNav (breadcrumb), AssetHeader, QuoteBlock, ProfileBlock, StatisticsBlock, EarningsBlock, AnalystBlock, **MetricsBlock**
- **MetricsBlock:** Shows Regime/Escalation per timeframe + 11 core metrics. For free users (`isPaid=false`), values are blurred.

---

### 1.6 Twelve Data Integration

**File:** `apps/web/src/lib/twelvedata.ts`

**Phases implemented:**
- Phase 1: Quote + Logo
- Phase 2: Profile (description)
- Phase 3: Statistics (P/E, market cap, 52w, div yield) — equities
- Phase 4: Earnings (next date, last EPS vs estimate)
- Phase 5: Recommendations + Price target — equities

**Symbol mapping:** Some symbols are mapped for Twelve Data (e.g. EURUSD → EUR/USD, BTCUSD → BTC/USD).

---

### 1.7 Data Flow

| Data | Source | Used For |
|------|--------|----------|
| Asset list | `riApi.assets()` or `universe.json` | Explorer, symbol pages |
| Per-asset meta | `riApi.asset(symbol)` | Symbol page (asset_class, has_compute) |
| Quote, logo, profile, stats, earnings, analyst | Twelve Data API | Asset detail pages |
| Regime, escalation, 11 metrics | Compute API (future) | MetricsBlock, ScreenerTable — not wired yet |

---

### 1.8 Key Files Reference

| File | Purpose |
|------|---------|
| `apps/web/src/app/(public)/page.tsx` | Landing page |
| `apps/web/src/app/(app)/explorer/page.tsx` | Explorer hub + drill-down |
| `apps/web/src/app/(app)/explorer/[symbol]/page.tsx` | Asset detail page |
| `apps/web/src/lib/loadAssets.ts` | Load assets from API or universe.json |
| `apps/web/src/lib/assetTypes.ts` | AssetItem type, assetClassDisplayName |
| `apps/web/src/lib/metrics.ts` | METRICS_11, RegimeState |
| `apps/web/src/components/symbol/ScreenerTable.tsx` | Table with filters, pagination |
| `apps/web/src/components/symbol/MetricsBlock.tsx` | Regime + 11 metrics (blurred for free) |
| `apps/web/src/components/symbol/LayoutEquities.tsx` | Equities asset page layout |
| `apps/web/src/components/layout/PublicLayout.tsx` | Public pages header/footer |
| `apps/web/src/components/dashboard/AppShell.tsx` | App sidebar + header |

---

## Part 2: Where We Stand Now

### 2.1 Current Explorer Flow

```
User visits /explorer
    ↓
Sees asset class cards (Core Macro + Earnings)
    ↓
Clicks "FX" (or any class)
    ↓
URL: /explorer?asset_class=FX
    ↓
ScreenerTable shows ONLY FX assets
    ↓
User can search, change page size (25/50/100/200)
    ↓
Clicks "Open" → /explorer/EURUSD
```

**Limitations:**
- No way to see all assets at once
- No cross-asset-class screening
- Asset class is a required drill-down, not a filter
- No saved screens (presets)
- No price charts in the table
- Symbol/name are not clearly clickable (only "Open" link)

---

### 2.2 What Exists vs What’s Missing

| Feature | Status |
|---------|--------|
| Explorer with asset class cards | ✅ Done |
| Drill-down to single asset class | ✅ Done |
| ScreenerTable (search, asset class filter, pagination) | ✅ Done |
| Regime/metric columns (blurred for free) | ✅ Done |
| Asset detail pages with Twelve Data | ✅ Done |
| MetricsBlock on asset pages | ✅ Done |
| **Unified screener (all assets, asset class = filter)** | ❌ Not done |
| **Cross-asset-class results** | ❌ Not done |
| **Filters: price, volume, earnings, fundamentals, our metrics** | ❌ Not done |
| **Saved screens (presets)** | ❌ Not done |
| **Clickable symbol/name → asset page** | ⚠️ Partial (only "Open" link) |
| **Small price chart per row** | ❌ Not done |
| **Twelve Data data in screener** | ❌ Not done |

---

## Part 3: Plan Moving Forward

### 3.1 Target: Unified Explorer Screener

**Goal:** One Explorer page with a single screener. Asset class is one filter among many. Results can include assets from any combination of asset classes.

**Flow:**
```
User visits /explorer
    ↓
Sees filter panel + results table
    ↓
Default: Asset class = "Any" → all assets
    ↓
User applies filters (price, volume, earnings, fundamentals, our metrics)
    ↓
Results update (can span FX + Equities + Crypto, etc.)
    ↓
Symbol and name are clickable → /explorer/[symbol]
    ↓
Each row has a small price chart (when data available)
    ↓
User can save screen → preset (localStorage or API)
```

---

### 3.2 Implementation Phases

#### Phase A: Restructure Explorer (Unified View)

1. **Change Explorer page logic**
   - Remove asset-class drill-down as the primary flow
   - Always show the screener with **all assets** by default
   - Asset class becomes a filter: "Any" or a specific class

2. **Optional: Keep asset class cards**
   - As shortcuts that set the asset-class filter and show results
   - Or remove them and rely only on the filter dropdown

**Files to touch:** `apps/web/src/app/(app)/explorer/page.tsx`

---

#### Phase B: Enrich Data for Screening

1. **Extend AssetItem or create ScreenerRow**
   - Add: price, volume, sector, industry, market_cap, pe, dividend_yield, next_earnings_date, etc.
   - Source: Twelve Data (quote, statistics, earnings, profile)

2. **Data loading strategy**
   - Option A: Batch-fetch Twelve Data for all assets when Explorer loads (may be slow for large universes)
   - Option B: Lazy-load per asset class or on filter change
   - Option C: Backend API that pre-aggregates screener data

**Files to touch:** `apps/web/src/lib/loadAssets.ts`, `apps/web/src/lib/assetTypes.ts`, `apps/web/src/lib/twelvedata.ts`

---

#### Phase C: Filter Panel

1. **Filters to implement**
   - Asset class (Any, FX, Equities, Crypto, …)
   - Price range (min, max)
   - Volume (min)
   - Next earnings (date range or "has upcoming")
   - Fundamentals: P/E range, market cap range, dividend yield
   - Sector, industry (from Twelve Data)
   - Our metrics (when compute is wired): regime, escalation, each of 11 metrics

2. **UI**
   - Collapsible filter panel
   - Dropdowns and range inputs
   - "Clear filters" and "Apply"

**Files to touch:** `apps/web/src/components/symbol/ScreenerTable.tsx` or a new `ExplorerFilters.tsx`

---

#### Phase D: Clickable Names & Charts

1. **Clickable symbol and name**
   - Make both link to `/explorer/[symbol]`
   - Style as links (e.g. underline, brand color)

2. **Small price chart**
   - Fetch OHLC from Twelve Data time_series (or equivalent)
   - Render a sparkline per row (e.g. lightweight-charts or Recharts)
   - Include volume if available
   - Start with placeholder if needed

**Files to touch:** `apps/web/src/components/symbol/ScreenerTable.tsx`, new `SparklineChart.tsx`

---

#### Phase E: Saved Screens (Presets)

1. **Data model**
   - Preset = { id, name, filters: { asset_class, price_min, price_max, ... } }

2. **Storage**
   - MVP: `localStorage`
   - Later: API + DB for cross-device

3. **UI**
   - "My Presets" dropdown: Save current, Load, Edit, Delete
   - Apply preset = set filter state from saved config

**Files to touch:** New `usePresets.ts` hook, `ScreenerTable.tsx` or filter panel

---

### 3.3 Suggested Order of Work

| Step | Task | Dependency |
|------|------|------------|
| 1 | Phase A: Unified Explorer (asset class = filter, show all assets) | None |
| 2 | Phase D.1: Clickable symbol/name | None |
| 3 | Phase B: Enrich assets with Twelve Data for screener | None (can start) |
| 4 | Phase C: Add price, volume, earnings, fundamental filters | Step 3 |
| 5 | Phase E: Saved presets (localStorage) | Step 1 |
| 6 | Phase D.2: Small price chart | Twelve Data time_series |
| 7 | Wire our metrics filters | Compute API |

---

### 3.4 Data Contracts (For Implementation)

**AssetItem (current):**
```ts
{ symbol, name, asset_class, has_compute? }
```

**ScreenerRow (proposed, extends AssetItem):**
```ts
{
  symbol, name, asset_class, has_compute?,
  // Twelve Data
  price?: number,
  volume?: number,
  change_pct?: number,
  sector?: string,
  industry?: string,
  market_cap?: number,
  pe?: number,
  dividend_yield?: number,
  next_earnings_date?: string,
  // Our compute (when available)
  regime?: string,
  escalation?: number,
  metrics?: Record<string, number>
}
```

**Preset:**
```ts
{
  id: string,
  name: string,
  filters: {
    asset_class?: string,
    price_min?: number,
    price_max?: number,
    volume_min?: number,
    // ... etc
  },
  createdAt: string
}
```

---

## Part 4: Quick Reference — Route Map

| Route | Layout | Description |
|-------|--------|--------------|
| `/` | Public | Landing |
| `/explorer` | App | Explorer hub + screener |
| `/explorer?asset_class=X` | App | Screener filtered by asset class (current) |
| `/explorer/[symbol]` | App | Asset detail page |
| `/overview` | App | Global Overview |
| `/alerts` | App | Alerts Center |
| `/market-map` | App | Market Map |
| `/audit` | Public | Audit page |
| `/methodology` | Public | Methodology |
| `/pricing` | Public | Pricing |
| `/asset-coverage` | Public | Redirects to `/explorer` |
| `/asset-coverage/[assetClass]` | Public | Redirects to `/explorer?asset_class=X` |

---

## Part 5: How to Use This Doc

- **Catching up:** Read Part 1 (history) and Part 2 (current state).
- **Planning work:** Use Part 3 (plan) and the suggested order.
- **Implementing:** Use the file references in 1.8 and the data contracts in 3.4.
- **Orientation:** Use Part 4 (route map) and the tables in 2.2.

When in doubt, return to this document and re-anchor on the target: **one unified Explorer screener with asset class as a filter, cross-asset results, full filter set, clickable names, charts, and saved presets.**
