# Regime Engine SaaS – DB Schema v1 (Deterministic Core)

**Purpose:** SaaS multi-tenant DB schema (tenancy, auth, billing, assets, engine runs). Use when building or extending the SaaS layer.

## 1) Tenancy
### tenants
- id (uuid, pk)
- name (text)
- created_at (timestamptz)

### tenant_users
- tenant_id (uuid, fk -> tenants.id)
- user_id (uuid, fk -> users.id)
- role (text)  # owner/admin/member
- created_at (timestamptz)

## 2) Auth / Users
### users
- id (uuid, pk)
- email (text, unique)
- password_hash (text)  # if not using Supabase/Auth0
- created_at (timestamptz)
- last_login_at (timestamptz)

## 3) Billing
### plans
- id (text, pk)  # free, pro, fund
- name (text)
- price_monthly_cents (int)
- features_json (jsonb)

### subscriptions
- id (uuid, pk)
- tenant_id (uuid, fk)
- plan_id (text, fk -> plans.id)
- status (text)  # active/trialing/canceled/past_due
- started_at (timestamptz)
- ends_at (timestamptz)
- stripe_customer_id (text)
- stripe_subscription_id (text)

## 4) Assets & Data
### assets
- id (text, pk)  # SPY, QQQ, NVDA, BTCUSD, XAUUSD...
- name (text)
- asset_class (text)  # equity/crypto/commodity/fx
- calendar (text)  # trading_252 / calendar_365
- is_active (bool)

### price_bars
- asset_id (text, fk -> assets.id)
- date (date)
- open (double)
- high (double)
- low (double)
- close (double)
- adj_close (double, nullable)
- volume (double, nullable)
- source (text)  # twelve_data/manual
- ingested_at (timestamptz)
PRIMARY KEY (asset_id, date)

## 5) Engine Runs (Deterministic Releases)
### engine_releases
- id (uuid, pk)
- tenant_id (uuid, fk)
- asset_id (text, fk)
- release_date (date)
- version (text)  # v1, v2...
- git_commit (text)
- data_sha256 (text)
- env_json (jsonb)
- created_at (timestamptz)

### engine_outputs_daily
- release_id (uuid, fk -> engine_releases.id)
- date (date)
- regime (text)
- confidence (double)
- conviction (text)
- escalation_v2 (double, nullable)
- risk_level (double, nullable)
- realized_vol (double, nullable)
- vrs (double, nullable)
- iix (double, nullable)
- dsr (double, nullable)
- ss (double, nullable)
- mb (double, nullable)
- lq (double, nullable)
PRIMARY KEY (release_id, date)

## 6) User Preferences
### user_asset_settings
- tenant_id (uuid, fk)
- user_id (uuid, fk)
- asset_id (text, fk)
- settings_json (jsonb)  # watchlist flags, chart defaults, alerts
- created_at (timestamptz)
PRIMARY KEY (tenant_id, user_id, asset_id)

## Notes
- Engine logic remains unchanged.
- DB stores only inputs (bars) + outputs (daily regime series) + reproducibility metadata.
