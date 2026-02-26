# Code Review — Email templates used vs NU (0055)

## Summary

Implementation adds identification of email templates that are used in application code vs not used (NU), exposes this via the admin templates API, shows " (NU)" in Settings for unused templates, and documents the list plus user journey coverage. **Follow-up fixes** added `UNUSED_EMAIL_TEMPLATES`, drift-detection tests, and non-blocking error message when template list fails to load.

## Implementation quality

- **Backend**: `USED_EMAIL_TEMPLATES`, `UNUSED_EMAIL_TEMPLATES`, and `list_templates_with_usage()` are clear; API returns `{ name, used }[]`. Comments reference `docs/EMAIL_TEMPLATES_USAGE.md`. Tests enforce that every template is in USED or UNUSED (no drift).
- **Frontend**: Settings dropdown uses the new shape and displays " (NU)" for unused; on templates load failure, `emailTemplatesError` is set and shown in the Email Templates card (amber, `role="alert"`). Card visible when list has items or when load failed; dropdown/Preview only when list has items.
- **Docs**: `docs/EMAIL_TEMPLATES_USAGE.md` and references (including tests) are up to date.

## Issues found

### Critical
- None.

### Major
- None.

### Minor

**Issue 1: Backend — `USED_EMAIL_TEMPLATES` can drift from code** *(fixed in follow-up)*
- **File**: `backend/app/services/email_service.py`
- **Location**: `USED_EMAIL_TEMPLATES` frozenset
- **Description**: Hand-maintained set could drift from actual template files.
- **Fix**: Added `UNUSED_EMAIL_TEMPLATES`; tests `test_list_templates_with_usage_deposit_cleared_not_used` and `test_list_templates_with_usage_every_template_classified` ensure every template is in USED or UNUSED.

**Issue 2: Frontend — fallback when templates load fails** *(fixed in follow-up)*
- **File**: `frontend/src/pages/SettingsPage.tsx`
- **Location**: `adminApi.getEmailTemplates().catch(() => [])`
- **Description**: On failure, user saw empty dropdown with no error message.
- **Fix**: `emailTemplatesError` state and in-card message (amber, `role="alert"`); card shown when error or when list has items.

**Issue 3 (optional): Stale `selectedTemplate` after fail then success** *(fixed)*
- **File**: `frontend/src/pages/SettingsPage.tsx`
- **Location**: `loadData`, `selectedTemplate` state
- **Description**: If templates load fails then a later load succeeds, the previous `selectedTemplate` could be missing from the new list.
- **Fix**: When the new list has items, set `selectedTemplate` to the first item if current selection is empty or not in the new list (`names.has(selectedTemplate)`).

## Data alignment

- API returns `templates: [{ name: string, used: boolean }]`; frontend expects the same. No snake_case/camelCase mismatch (backend can return snake_case; FastAPI typically converts to camelCase if configured — verified: frontend uses `t.name` and `t.used`, so if API sends `name`/`used` we are aligned).

## Plan / scope

No plan was provided. Scope was: (1) identify templates used in code vs not, (2) mark unused as NU in frontend Settings, (3) identify if any template is missing from user journey. All three are done. Follow-up addressed Issue 1 (drift test + `UNUSED_EMAIL_TEMPLATES`) and Issue 2 (error message on templates load failure).

## Security / testing

- No new auth surface; admin-only endpoint unchanged.
- **Tests**: `test_list_templates_with_usage_deposit_cleared_not_used` and `test_list_templates_with_usage_every_template_classified` added; all 19 tests in `test_email_lifecycle.py` pass. Drift test ensures every template file is in USED or UNUSED.

## UI/UX and interface analysis

- **Design tokens**: Error message uses `text-amber-400` (design system); card uses `bg-navy-800/50`, `border-navy-700`, `text-navy-400`. No hard-coded hex, no `slate-*`/`gray-*`.
- **Accessibility**: Error message has `role="alert"`. Dropdown and Preview are hidden when list is empty, avoiding an empty select.
- **States**: Loading (existing Settings loading state); error (non-blocking, in-card); empty list (card shown when error, no dropdown).
- **Theme**: Tailwind tokens only; compatible with light/dark if applied at root.

## Recommendations

1. Keep `USED_EMAIL_TEMPLATES` and `UNUSED_EMAIL_TEMPLATES` in sync when adding/removing templates or send_* calls (documented in code and `docs/EMAIL_TEMPLATES_USAGE.md`).
2. ~~Optional (Issue 3)~~ Done: when setting `emailTemplates` to a new list, if the current `selectedTemplate` is not in the new list, set `selectedTemplate` to the first item.

---

**Conclusion**: Implementation and follow-up fixes are correct and complete. No Critical or Major issues. All Minor issues (1, 2, 3) have been addressed.

---

## Follow-up (fixes and recommendations implemented)

- **Issue 1**: Added `UNUSED_EMAIL_TEMPLATES` in `email_service.py`; added tests `test_list_templates_with_usage_deposit_cleared_not_used` and `test_list_templates_with_usage_every_template_classified` so every template must be in USED or UNUSED (detects drift).
- **Issue 2**: When `getEmailTemplates()` fails, frontend now sets `emailTemplatesError` and shows a non-blocking message in the Email Templates card (amber text, `role="alert"`). Card is shown when there are templates or when load failed. Dropdown and Preview are hidden when list is empty.
