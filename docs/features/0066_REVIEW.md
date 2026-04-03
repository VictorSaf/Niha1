# Code Review — Priority 0: Spread 0.1 when MM introduces order

## Summary

Implementation adds **Priority 0 (spread narrowing)** to the auto-trade executor chain so that when a market maker introduces a new order, the first priority is to achieve target spread (0.1 EUR for CEA cash). **Priority 0 can exceed the established liquidity level** — when spread > target, the executor places spread-narrowing orders even when at_target or above_target.

## Files Modified

- `backend/app/services/auto_trade_executor.py` — Priority 0 in `determine_priority_price`; at_target/above_target override when spread > target
- `app_truth.md` — Updated Auto Trade section for five-priority algorithm and spread-first behavior

## Implementation Quality

Implementation is correct and focused. The new priority:
- Uses `best_bid` and `best_ask` to compute spread
- Uses `avg_spread` from market settings (fallback 0.1 for cash, 0.0050 for swap)
- Places BID at `best_bid + tick` when BUY and spread > target
- Places ASK at `best_ask - tick` when SELL and spread > target
- Runs before gap fill, alignment, and level rebalance
- Overrides liquidity status: when at_target or above_target, if spread > target, still places spread-narrowing order

## Issues Found

### Critical
None.

### Major
None.

### Minor (addressed)
- ~~For swap market, `target_spread` default 0.001 is reasonable; `avg_spread` in DB for EUA_SWAP is typically 0.0050.~~ Fixed: swap fallback set to 0.0050 to match EUA_SWAP typical avg_spread and DEFAULT_MARKET_SETTINGS; logic still uses `market_settings.avg_spread` when present.

## Recommendations

- None. Implementation matches the stated requirement.
- Backend tests pass (49 passed, 5 skipped excluding pdf renderer).
- No UI changes; no design system review needed.

## Confirmation

Plan fully implemented:
- Spread 0.1 (or `avg_spread`) is now the first priority when MM introduces a new order
- Priority 0 exceeds liquidity level — spread-narrowing orders placed even when at_target or above_target
