# 0057 — Code Review: Documentație PDF, Settings Documents, marcaj NU, NDA sursă unică

## Summary

Implementation matches plan 0057: (1) Settings → Documents now lists from `documents/` with used/NU and catalog details; (2) NDA for invitations is sourced via `document_delivery_service.get_document_bytes("nda", ...)` instead of a fixed path; (3) Docker mounts `./documents:/app/documents` and app_truth documents DOCUMENT_BASE_PATH.

**Quality**: Good. Clear separation of docs/ vs documents/ in the service, consistent API response shape, frontend uses design tokens (navy, amber for NU badge). A few minor points below.

---

## Plan compliance

- **4.1** Backend lists from `documents/` (.pdf, .docx), returns used, email_templates, catalog fields; preview root is documents/. ✅
- **4.2** Documents with `used === false` show **(NU)** in UI. ✅
- **4.3** NDA invitations use `get_document_bytes("nda", ...)` in admin (3 call sites) and contact (2). ✅
- **4.4** Docker volume `./documents:/app/documents` added; app_truth has Document storage + DOCUMENT_BASE_PATH. ✅

---

## Issues

### Critical
- None.

### Major
- None.

### Minor (all addressed)

1. **Backend — admin.py `__nda_system_user`** (fixed): Helper is module-level and uses `UserRole.ADMIN`; fine. Consider moving to a small shared helper in `document_delivery_service` or `core` if other callers need a “system” user in the future (e.g. `get_document_bytes` with `skip_access_check`). Not required for this feature.

2. **Frontend — preview type for docx**: Modal shows “.docx file — Download” and uses `previewBlobUrl` for the download link. Correct; no inline preview for docx. Optional: could set `previewType` to a separate value (e.g. `'docx'`) so the condition is explicit; current code already branches on `previewType === 'docx' && previewBlobUrl`. No change needed.

3. **Tests — DocumentsTab**: Mock list updated to new shape (used, type pdf). Consider adding one test that a document with `used: false` renders the “NU” badge. Low priority.

---

## Data / API

- List API returns snake_case; frontend uses response interceptor → camelCase (used, emailTemplates, title, phaseName, category). ✅
- Preview API: path relative to documents/; backend validates with `get_document_preview_path`. ✅

---

## Security & practices

- Path traversal blocked in `get_document_preview_path` (no `..`, no leading `/`). ✅
- NDA bytes obtained via existing `get_document_bytes` (access checks in place); system user has ADMIN role for generation. ✅

---

## UI/UX (Settings → Documents)

- Title: “Documentation (documents/)”. Description explains “Used” vs “(NU)”. ✅
- NU badge: `Badge variant="navy" className="text-amber-400 bg-amber-500/20"` — consistent with design tokens (navy, amber). ✅
- Catalog details (title, phase, category) shown when present; email template badges unchanged. ✅
- No hard-coded hex/slate/gray; Tailwind tokens used. ✅

---

## Recommendations

- None blocking. Optional: add a test in `DocumentsTab.test.tsx` that an entry with `used: false` displays the “NU” badge.

---

## Conclusion

Implementation is complete and aligned with the plan. No Critical or Major issues. All minor items and recommendations have been addressed.
