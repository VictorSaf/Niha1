# Code Review — Reset Market Makers fixes

## Summary

Backend fixes in `reset_all_market_makers`:

1. **Transaction order**: Audit ticket is created **before** `db.commit()` so it is persisted (same transaction).
2. **FK constraint**: Before deleting `cash_market_trades`, delete from `commission_ledger` where `cash_market_trade_id` references those trades, to avoid `ForeignKeyViolationError` (commission_ledger_cash_market_trade_id_fkey).

## Implementation quality

- **Changes**: (1) Create ticket in same transaction; (2) subquery `mm_trades_subq` for MM-related trade IDs; (3) delete `CommissionLedger` rows whose `cash_market_trade_id` is in that set; then delete `cash_market_trades` as before.
- **Scope**: Only `backend/app/api/v1/market_maker.py`; no UI, no schema, no new tests.

## Issues found

| Severity | Issue | File:Line |
|----------|--------|-----------|
| None | — | — |

No Critical, Major, or Minor issues.

## Recommendations

- Optional: integration test for `POST /admin/market-makers/reset-all` (auth + valid password, verify ticket and balances).

## Plan

No plan file; ad-hoc bugfixes. Implementation matches intent.
