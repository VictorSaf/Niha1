# Code Review: Custom Arrow for All Selects

## Summary
Applied custom dropdown arrow with 12px gap from right edge to all select elements across the application. Native browser arrow ignores padding, so `appearance: none` + background-image was used.

## Implementation
- **`.form-select`** (index.css): Added appearance-none + custom chevron background, `right 0.75rem` positioning → all form-selects updated
- **`.select-arrow-spaced`**: For selects without w-full (e.g. DocumentLibrary, KycFormWizard PEP role)
- **`.select-arrow-spaced-compact`**: For compact selects (text-xs, py-1.5)

## Files Modified
1. `frontend/src/index.css` – form-select, select-arrow-spaced, select-arrow-spaced-compact
2. `frontend/src/pages/DocumentLibraryPage.tsx` – select-arrow-spaced
3. `frontend/src/components/onboarding/KycFormWizard.tsx` – form-select / select-arrow-spaced
4. `frontend/src/components/dashboard/PriceAlerts.tsx` – select-arrow-spaced-compact
5. `frontend/src/components/admin/RoleSimulationFloater.tsx` – select-arrow-spaced-compact
6. `frontend/src/components/backoffice/AllTicketsTab.tsx` – select-arrow-spaced-compact
7. `frontend/src/pages/ThemePage.tsx` – removed duplicate ChevronDown (form-select has built-in arrow)
8. `frontend/src/pages/ThemeSectionPage.tsx` – ChevronDown right-4 → right-6

## Coverage
All selects now use either form-select (with custom arrow), select-arrow-spaced, or select-arrow-spaced-compact. No native arrow remains.

## Issues
None.
