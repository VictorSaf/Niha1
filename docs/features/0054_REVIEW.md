# Code Review — 0054 Document attachments in client journey emails

## Summary of implementation quality

The implementation adds document attachments to two journey emails using the existing Document Library catalog and PDF generators. **account_approved** receives generated PDFs (MSA, Custody, Fee Schedule, Risk Disclosure, Derivatives) pre-filled with client data; **deposit_announced** receives static operational docs (Bank Confirmation Letters, Registry Overview). A new `document_delivery_service` returns bytes for a given `document_id` and user (with optional role override). Email service methods accept optional `attachments`; backoffice and deposits build attachments and pass them. NDA remains only at the beginning (unchanged). Design aligns with `docs/DOCUMENT_EMAIL_MAPPING.md` and legal/reasonable document delivery practices.

---

## Plan compliance

| Requirement | Status |
|-------------|--------|
| Attach documents at correct steps (account_approved, deposit_announced) | Met |
| Pre-filled with client and NIHA data where generators support it | Met |
| NDA only at beginning (pre_nda, introducer_nda) | Met (unchanged) |
| No artificial limits; legal/reasonable needs | Met (mapping doc + research) |

---

## Issues

### Critical
- None.

### Major
- None.

### Minor

1. **Optional: centralise catalog in services**  
   `document_delivery_service` imports `DOCUMENT_CATALOG` and `user_has_min_role` from `app.api.v1.documents`. If the API module grows, consider moving the catalog and role helpers to `app.services.document_catalog` so both the router and the delivery service import from one place and the API layer stays thin.

2. **Template sample data**  
   `TEMPLATE_SAMPLE_DATA` for `account_approved.html` and `deposit_announced.html` was updated with `documents_attached: True` so admin previews show the attachment message. No code issue; just noted for consistency.

---

## Other checks

- **Bugs:** Attachment building is best-effort (log and continue on ValueError/FileNotFoundError); email still sends if some or all attachments fail. Appropriate for fire-and-forget.
- **Data alignment:** Attachments use `{"filename": str, "content": bytes}` matching existing `_send_email` contract.
- **app_truth.md:** §4 (Integrations / Email) updated with document-attachments behaviour and doc references.
- **Error handling:** Backoffice and deposits catch ValueError and FileNotFoundError per document; approval/deposit flow does not fail if attachment generation fails.
- **Security:** Document access is enforced by `get_document_bytes` (role/min_role and admin_only). No user-controlled paths.

---

## Recommendations

1. Keep `docs/DOCUMENT_EMAIL_MAPPING.md` in sync if new emails or document IDs are added to the journey.
2. (Optional) Add integration tests that approve a user and assert the approval email includes the expected attachment count or content-type when document generation is available.

---

**Review complete.** No Critical or Major issues. Implementation is ready to ship.
