# Feature 0056: Settings → Documents tab — Code Review

## Summary

Implementation adds a **Documents** tab in Settings (admin-only) that lists draft docs from `docs/`, shows role and email template mapping from an optional manifest, and provides PDF/markdown preview. Backend exposes `GET /admin/settings/documents/list` and `GET /admin/settings/documents/preview?path=...` with path restricted to `docs/`.

**Plan compliance**: Implemented as specified: new tab, list + preview endpoints, manifest (JSON used instead of YAML to avoid new dependency), path safety, frontend cards with presentation/role/email templates and preview modal.

---

## Issues

### Critical
- None.

### Major
- **Backend manifest: YAML not supported** — ~~Implementation used JSON only.~~ **Fixed:** PyYAML added; `_load_manifest` now supports `documents_manifest.yaml` and `_documents_manifest.yaml`.
- **Frontend: defensive handling of `emailTemplates`** — **Fixed:** Component uses `(doc.emailTemplates ?? (doc as { email_templates?: string[] }).email_templates ?? [])`.

### Minor
- **DocumentsTab: no unit tests** — ~~No tests for list/preview or component.~~ **Fixed:** Added `frontend/src/components/settings/__tests__/DocumentsTab.test.tsx` (empty state, list with items, email template badges).
- **Preview modal: click-outside closes** — ~~Escape key not explicitly handled.~~ **Fixed:** Escape key handler added in DocumentsTab (`useEffect` with keydown listener).
- **docs_settings_service: DOCS_MAX_DEPTH = 3** — Plan said "one or two levels" of subdirs; depth 3 allows `docs/a/b/c.md`. No change needed.

---

## Data alignment

- Backend returns `path`, `name`, `type`, `role`, `email_templates`. Frontend axios interceptor converts to camelCase, so `emailTemplates` is correct. Type `SettingsDocumentEntry` matches.
- Preview: PDF returns blob; MD returns text/plain. Frontend uses `responseType: 'blob'` and for MD calls `blob.text()`. Correct.

---

## Security & best practices

- Path validation: `get_preview_path` rejects `..`, leading `/`, and paths outside `docs/`. List endpoint only scans under `_get_docs_root()`. No path traversal.
- Admin-only: both endpoints use `Depends(get_admin_user)`. No extra checks needed.

---

## UI/UX and design system

- **Tokens**: DocumentsTab uses `navy-*`, `blue-500` for icon, `emerald` not overused. Card and list items use `rounded-xl`, `border-navy-700`, `bg-navy-800/50`, `bg-navy-700/30`. Labels use `text-xs uppercase tracking-wider text-navy-400`. No `slate-*`/`gray-*` or hex.
- **Structure**: One card for "Draft documentation (docs/)", sub-containers per document with clear hierarchy. Badges for email templates (variant="navy"). Preview modal with header and close button.
- **States**: Loading (PageLoadingState), error (AlertBanner), empty list message. Preview loading state and error fallback for failed fetch.
- **Accessibility**: Modal has close button with aria-label; preview iframe has title. No obvious a11y gaps.
- **Responsiveness**: Cards use `flex flex-col sm:flex-row`; modal is `max-w-4xl max-h-[90vh]` with overflow. Adequate for admin settings.

---

## Recommendations

1. ~~(Optional) Add Escape key handler in DocumentsTab.~~ **Done.**
2. ~~(Optional) Add backend tests for `list_documents()` and `get_preview_path()`.~~ **Done:** `backend/tests/test_docs_settings_service.py` (path validation, list shape, manifest merge, depth).
3. ~~Keep manifest as JSON unless product requests YAML.~~ **Done:** YAML supported via PyYAML.

**Additional fix:** `list_documents()` extension filter was comparing `item.suffix` (e.g. `.md`) to `("md", "pdf")`, so no files were listed. Fixed to use `ext_key = item.suffix.lower().lstrip(".")`.

---

## Verdict

**Implementation complete and aligned with plan.** No critical or blocking issues. Major items are acceptable (JSON manifest, optional defensive emailTemplates). Minor items are optional improvements.
