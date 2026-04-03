# Review: Audit fixes (NDA attachment, PDF test, trading-compact colors)

## Summary

Implementation addresses the three audit recommendations:

1. **Introducer NDA attachment** — Email is sent only when NDA PDF is successfully generated; otherwise the email is skipped and an error is logged. Admin "Send NDA" endpoints return 503 when NDA generation fails.
2. **PDF test collection** — WeasyPrint check catches `OSError`; `render_pdf` and `generate_nda_pdf` are imported only when WeasyPrint is available, so pytest collection succeeds without libgobject.
3. **trading-compact.css** — All `rgb()` usages replaced with design token variables (`var(--color-*)`, `var(--input-placeholder)`, etc.).

## Implementation quality

- **contact.py**: Two flows (introducer-nda-request and introducer-request) now send the introducer NDA invitation only when `nda_attachments` is truthy; broadcast and success log happen only in that case; else an error is logged.
- **admin.py**: Create-user TRODUCER branch skips sending the invitation when NDA generation fails and logs an error. Send-NDA endpoints (introducer and buyer) raise `HTTPException(503)` when NDA cannot be generated or email fails, so the admin sees a clear error.
- **test_pdf_renderer.py**: `_has_weasyprint` catches `(ImportError, OSError)`; conditional imports avoid loading `nda_generator` when WeasyPrint is missing; `test_nda_generator_signature_preserved` is marked `@_skip_weasyprint`.
- **trading-compact.css**: Uses `--color-background`, `--color-surface`, `--color-border`, `--color-text-muted`, `--color-bid-hover`, `--color-ask`, `--color-ask-hover`, `--color-bid-bg`, `--color-ask-bg`, `--color-bid-light`, `--color-ask-light`, `--input-placeholder`, `--color-warning`, `--color-primary-active`, `--color-primary-dark`.

## Issues found

| Severity | None |
|----------|------|

No Critical, Major, or Minor issues. Implementation is focused and consistent with existing patterns.

## Recommendations

- Consider adding a health or admin check that verifies NDA PDF generation (e.g. a lightweight endpoint or startup check) so missing WeasyPrint/deps are detected early in deployment.
- Optional: in contact flows, when NDA generation fails, consider returning a 503 or a specific message to the client so they can retry, instead of only logging (current behavior keeps the request successful but no email sent).

## Plan compliance

No formal plan; changes follow the audit recommendations. All three items are implemented.
