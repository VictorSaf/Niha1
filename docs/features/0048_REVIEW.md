# Code Review: CEAPriceChart – cap candles, disable selection

## Summary

1. **Cap candles:** Max 120 candles displayed to prevent unreadable agglomeration ("mamaliga")
2. **Disable selection:** Tooltip removed, `select-none`, `onMouseDown` preventDefault on chart area
3. **No internal div selection:** preventDefault stops browser from selecting internal elements on click

**Modified file:** `frontend/src/components/cash-market/CEAPriceChart.tsx`

## Implementation Quality

- `MAX_CANDLES_DISPLAY = 120`; `displayedPoints = points.slice(-MAX_CANDLES_DISPLAY)` – last 120 candles shown
- `onMouseDown={(e) => e.preventDefault()}` on chart container only (header/dropdown unaffected)
- `select-none` on root and chart wrapper
- Header controls (interval selector) remain interactive

## Issues Found

**Critical:** 0  
**Major:** 0  
**Minor:** 0

## UI/UX Analysis

- Chart stays readable with bounded candle count
- No selection or focus on chart area; dropdown works normally

## Recommendation

Change complete. No fixes required.
