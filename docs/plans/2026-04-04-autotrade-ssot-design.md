# Auto-Trade Single Source of Truth — Design

**Date:** 2026-04-04

## Goal

Eliminate the dual-UI confusion in auto-trade configuration. `AutoTradeMarketSettings` becomes the single source of truth for all executor parameters. The Market Makers → Auto Trade Rules tab becomes read-only status. Three previously hardcoded executor parameters are promoted to DB columns.

## Problem Statement

Two UI surfaces currently suggest they both control auto-trade behavior:
1. **Market Makers → Auto Trade Rules** — editable per-MM rules (interval, quantity, deviation)
2. **Auto Trade page** — editable market-level settings

In reality, the Liquidity Engine executor ignores most `AutoTradeRule` fields and reads from `AutoTradeMarketSettings`. Three parameters are hardcoded in the executor and not configurable from any UI.

## Approach: Additive migration + UI consolidation (Approach 1)

### What changes

**Backend**
- One Alembic migration adds 3 columns to `auto_trade_market_settings`:
  - `alignment_correction_factor FLOAT DEFAULT 0.6` — mean-reversion weight for P2 alignment
  - `alignment_threshold_ticks INT DEFAULT 2` — ticks from mid before P2 triggers
  - `level_rebalance_depth INT DEFAULT 5` — depth levels scanned for P3 rebalancing
- `AutoTradeMarketSettings` model: 3 new fields
- `AutoTradeMarketSettingsUpdate` + `AutoTradeMarketSettingsResponse` schemas: 3 new fields
- `auto_trade_executor.py`: replace 3 hardcoded literals with `settings.*`

**Frontend**
- Auto Trade page: add "Advanced" collapsible section with 3 new fields
- Market Makers → Auto Trade Rules tab: read-only status table (rule ID, side, enabled, active orders, last execution). Remove all edit controls.

### What does NOT change

- `AutoTradeRule` table stays in DB (executor coordination — tracks active orders per MM per rule)
- `AutoTradeSettings` table stays in DB (dead code, no migration cost to drop it now)
- All existing API endpoints unchanged
- No route additions or removals

## Data Flow

```
Auto Trade UI ──► PUT /auto-trade/market-settings/{key} ──► AutoTradeMarketSettings (DB)
                                                                    │
                                                         Executor reads all params
                                                         (interval, quantities, deviation,
                                                          correction_factor, threshold_ticks,
                                                          rebalance_depth)

Market Makers UI ──► GET /auto-trade/rules (read-only) ──► AutoTradeRule (status only)
```

## Priority Engine (unchanged logic, configurable params)

| Priority | Name | Key param (now configurable) |
|----------|------|------------------------------|
| P0 | Spread narrowing | `avg_spread`, `tick_size` |
| P1 | Gap fill | `tick_size` |
| P2 | Price alignment | `alignment_correction_factor`, `alignment_threshold_ticks` |
| P3 | Level rebalancing | `level_rebalance_depth` |
| P4 | Normal liquidity | `target_liquidity`, `volume_*` |

## Migration Safety

- All 3 new columns have `DEFAULT` values matching current hardcoded literals
- Existing rows get defaults automatically on migration
- No data loss, no downtime, no backfill needed

## Files Touched

| File | Change |
|------|--------|
| `backend/alembic/versions/2026_04_04_autotrade_ssot.py` | New migration |
| `backend/app/models/models.py` | 3 fields on `AutoTradeMarketSettings` |
| `backend/app/schemas/auto_trade.py` | 3 fields on Update + Response schemas |
| `backend/app/services/auto_trade_executor.py` | Replace 3 hardcoded literals |
| `frontend/src/pages/AutoTradePage.tsx` | Add Advanced section with 3 fields |
| `frontend/src/components/admin/MarketMakerAutoTradeRules.tsx` (or equivalent) | Convert to read-only status table |
