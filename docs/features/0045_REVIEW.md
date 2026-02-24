# Code Review: Price History Charts Proportion Fix

**Feature**: Fix disproportionate Price History charts in Backoffice Settings (Price Scraping & Exchange Rate tabs).

**Plan**: N/A — ad-hoc UI fix requested by user.

**Files changed**: `frontend/src/pages/SettingsPage.tsx`

---

## Summary

Implementation fixes the inconsistent aspect ratio and font scaling of the Price History charts. Root cause: SVG used `preserveAspectRatio="none"` and `h-36`, causing different stretch when containers had different widths (e.g. 1216px vs 972px), which led to disproportionate axis fonts between the EUA EUR and CEA CNY graphs.

---

## Issues Found

| Severity | Count |
|----------|-------|
| **Critical** | 0 |
| **Major** | 0 |
| **Minor** | 0 (1 fixed) |

### Minor

1. ~~**Indentation** — `SettingsPage.tsx` L216–217: `onMouseMove` and `onMouseLeave` on the `<svg>` are indented less than other attributes.~~ **Fixed**

---

## Verification Checklist

| Item | Status |
|------|--------|
| Plan correctly implemented | N/A (no plan) |
| Obvious bugs | ✓ None |
| Data alignment (snake_case/camelCase) | ✓ Not applicable |
| `app_truth.md` respected | ✓ No conflicts |
| Over-engineering / file size | ✓ Minimal change |
| Syntax / style consistency | ✓ Minor indentation only |
| Error handling / edge cases | ✓ Unchanged (points.length &lt; 2 handled) |
| Security / best practices | ✓ No issues |
| Testing coverage | ✓ No new logic; existing behaviour preserved |

---

## UI/UX and Interface Analysis

**Design tokens**

- Uses `navy-200`, `navy-400`, `navy-500`, `navy-700`, `emerald-400`, `red-400` (Tailwind palette)
- Chart fill/line colors from `TREND_COLORS` (maps to `chartColors.ts` design tokens)
- No hex or `slate-*`/`gray-*` in new code

**Theme system**

- Components inherit theme; no new theme logic. Settings page uses dark navy tokens.

**Accessibility**

- Reset button has `title` attribute
- SVG is decorative/data; tooltip shows hovered values
- No ARIA regressions; keyboard usage unchanged

**Responsiveness**

- `w-full`, `aspect-[600/140]`, `min-h-[140px]` ensure consistent sizing across viewports
- `min-w-0` on grid items prevents overflow in flex/grid layouts
- `grid-cols-1` keeps charts stacked and equal width

**Design system alignment**

- Card/panel patterns match `frontend/docs/DESIGN_SYSTEM.md` (§ Panels, Spacing)
- Matches Settings UI patterns (Card, design tokens)

---

## Recommendations (implemented)

1. ~~Align `onMouseMove`/`onMouseLeave` indentation with other `<svg>` attributes.~~ ✓ Done
2. ~~Add `role="img"` and `aria-label="Price history chart for {sourceName}"` on the SVG.~~ ✓ Done

---

## Status

Implementation complete. All issues fixed; recommendations implemented.
