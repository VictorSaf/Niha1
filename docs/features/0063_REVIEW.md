# Code Review — 0063: Eliminate spacing between Subheader and SubSubHeader

## Summary

Implementation removes the visible gap between the Subheader bar and the SubSubHeader on Backoffice pages by:
1. Adding optional `renderSpacer` prop to `Subheader` so the spacer can be omitted when a SubSubHeader follows.
2. In `BackofficeLayout`, when SubSubHeader is shown: passing `renderSpacer={false}` and rendering a single spacer + SubSubHeader so content still starts below the fixed bar.
3. Giving `.subheader-bar` `min-height: var(--subheader-bar-min-height)` so the bar height matches the spacer and there is no visual gap.

No plan was attached; this was a direct fix from the audit.

## Implementation quality

- **Scope**: Changes are limited to Subheader, BackofficeLayout, and design-tokens.css. No unrelated code touched.
- **Backward compatibility**: `renderSpacer` defaults to `true`, so all other pages (Dashboard, Cash Market, etc.) keep current behavior.
- **Design tokens**: Uses existing `--subheader-bar-min-height`; no new tokens. No hardcoded colors or spacing.

## Issues found

### Critical
- None.

### Major
- None.

### Minor
- **BackofficeLayout**: The fragment `<>...</>` wrapping spacer + SubSubHeader could be a single wrapper div with a class (e.g. `subheader-subsubheader-block`) for consistency and future styling; not required for correctness.

## UI/UX and design system

- **design-tokens.css**: Only addition is `min-height: var(--subheader-bar-min-height)` on `.subheader-bar`, aligning bar height with the existing spacer variable.
- **Subheader.tsx**: New prop is optional and documented; conditional rendering of the spacer is clear.
- **BackofficeLayout.tsx**: Logic `renderSpacer={!showSubSub}` and the spacer + SubSubHeader fragment match the intended layout (no gap, content still pushed down).

## Recommendations

- Consider adding a short comment in BackofficeLayout above the fragment explaining that the spacer is rendered here (not inside Subheader) when SubSubHeader is present so the two bars sit flush.

## Confirmation

The fix was implemented as intended: spacing between Subheader and SubSubHeader is eliminated on Backoffice pages by aligning bar height with the spacer and omitting the spacer from Subheader when SubSubHeader is present, while still reserving space so main content starts below both bars.
