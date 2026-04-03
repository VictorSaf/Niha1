# Code Review: CEA Spread 0.1 + Internal Trade for Large Spread

## Summary

Implementation adds:
1. Migration `2026_03_01_cea_spread_0_1`: sets `avg_spread=0.1`, `tick_size=0.1` for CEA_BID/CEA_ASK
2. `place_random_order` (admin): Step 1a — when spread > 0.5 EUR, execute internal trade first; return early if success
3. `execute_rule` (auto_trade_executor): when `spread_priority_large_spread` (spread > 2×target), try internal trade first; return early if success

## Implementation Quality

- **Correctness**: Logic is sound. Internal trade consumes best bid and best ask between MMs, clearing wide spread levels; subsequent calls repopulate at target spread.
- **Consistency**: Threshold 0.5 EUR in place_random_order; 2×target in execute_rule. Both align with target spread 0.1.
- **Error handling**: Internal trade can fail (cooldown, no orders); fallback to limit-order path is correct.
- **Integration**: Uses existing `AutoTradeExecutor.execute_internal_trade`; no new dependencies.

## Issues Found

### Major
None.

### Minor (FIXED)
1. **Response keys** (admin place_random_order): ✅ Fixed — early return now uses `side="internal_trade"`, `market_maker=""`, `volume_eur` computed from price×quantity; frontend receives valid strings.
2. **market_key in place_random_order**: Acceptable — CEA_BID and CEA_ASK share same internal-trade cooldown for CEA cash. No change.

### Suggestions (IMPLEMENTED)
- ✅ **Configurable threshold**: Threshold derived from `avg_spread` — `max(0.5, avg_spread × 5)`; scales with settings.
- ✅ **Logging**: Added `logger.info` for spread reduction internal trade in both `place_random_order` and `execute_rule`.

## Plan Implementation

✅ Migration for avg_spread 0.1, tick_size 0.1
✅ place_random_order Step 1a — internal trade when spread > 0.5
✅ execute_rule — internal trade when spread_priority_large_spread

## Verification

- Migrations run successfully.
- Lint passes.
- Existing tests pass (admin/auto_trade/order tests).
