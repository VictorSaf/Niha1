# Feature 0046 — CEA Price Chart: Candlestick → Area Chart

## Summary

Replaced candlestick chart with a discreet area chart on Cash Market Pro. Chart is smaller, uses softer colors, and fits better with the platform.

## Implementation Quality

- **Scope**: CEAPriceChart, chartColors, CashMarketProPage layout
- **Approach**: CandlestickSeries → AreaSeries; softer emerald palette; reduced proportions

## Issues Found

### Critical
None.

### Major
None.

### Minor
1. **chartColors.ts**: `CANDLESTICK_COLORS` kept as alias for backward compat; no consumers remain. Can be removed in a follow-up cleanup.
2. **CEAPriceChart.tsx**: `glow-emerald` class on container—verify it does not add excessive glow in production.

## Design System Compliance

- **Colors**: Uses `CEA_PRICE_CHART_COLORS` (emerald500, navy-*, rgba) — no hardcoded hex beyond constants
- **Tailwind**: navy-*, emerald-500, no slate/gray
- **Tokens**: chartColors maps to design system; chart background transparent, grid/crosshair subdued
- **Theme**: Dark-first; chart inherits page theme

## Plan Implementation

Fully implemented:
1. Switched from CandlestickSeries to AreaSeries
2. Softer colors (emerald500, topColor 12% opacity)
3. Reduced chart proportions (row1: 45% | 28% | 27%; vertical: 52% | 48%)
4. Chart container: min-h 180px, max-h 280px
5. barSpacing 18, minBarSpacing 8 for less cramped display

## Recommendations

- Run frontend tests
- Optional: remove `CANDLESTICK_COLORS` export after confirming no imports
