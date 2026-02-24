# Code Review: Dropdown Arrow Padding Fix

## Summary
Added extra right padding (`pr-10` / `pr-8`) to native `<select>` elements that did not use the shared `.form-select` class, so the dropdown arrow is no longer cramped against the right edge.

## Implementation Quality
- **Scope**: 6 files modified
- **Consistency**: Aligns with `.form-select` (which already has `pr-10` in `index.css`)
- **Proportions**: Standard selects use `pr-10`, compact (text-xs) use `pr-8`

## Files Modified
1. `frontend/src/pages/DocumentLibraryPage.tsx` – Phase and Category filters (2 selects)
2. `frontend/src/components/onboarding/KycFormWizard.tsx` – PEP role, years of experience, annual volume (3 selects)
3. `frontend/src/components/dashboard/PriceAlerts.tsx` – Cert type, direction (2 selects)
4. `frontend/src/components/admin/RoleSimulationFloater.tsx` – Role simulation (1 select)
5. `frontend/src/components/backoffice/AllTicketsTab.tsx` – Category and status filters (2 selects)

## Issues Found
None (Critical/Major/Minor).

## UI/UX Analysis
- Uses existing design tokens (navy-900, navy-600, etc.)
- No hard-coded colors or `slate-*`/`gray-*`
- Matches `.form-select` padding convention in `index.css`

## Recommendations
None required.
