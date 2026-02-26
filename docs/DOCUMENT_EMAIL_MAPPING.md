# Document–Email Mapping (Client Journey)

This document defines **which platform documents are sent (attached) at which communication step** and at **which user role**, based on legal and operational best practices.

## Research summary (legal / reasonable needs)

- **Risk disclosure**: Must be provided **before** the financial service is delivered; "as soon as practicable" when it becomes apparent that a service will be provided (FCA COBS 2.2, ASIC-type practice). Clients should have adequate time to review before deciding.
- **MSA and Custody**: Should be reviewed and executed **before trading begins**; clients must accept terms before accessing or using services (common practice for trading/custody platforms).
- **Onboarding order**: KYC → legal documentation / contract execution → funding (FMSB-style sequence). Contracts and disclosures before first deposit/trade.

**Conclusion**: Send **contractual and risk documents when KYC is approved** (before funding/trading). Send **operational documents** (bank confirmations, registry overview) when the client enters the **funding phase** (announce deposit). **NDA** remains only at the very beginning (pre-NDA / introducer flows).

---

## Mapping: email template → role → attached documents

| Email template | User role when sent | Attached documents | Pre-filled with client/NIHA data |
|----------------|---------------------|--------------------|-----------------------------------|
| **pre_nda_invitation** | — (before account) | NDA | Generated via `document_delivery_service.get_document_bytes("nda", ...)` |
| **introducer_nda_invitation** | — (before account) | NDA | Same (generated NDA from document_delivery_service) |
| **account_approved** | APPROVED (KYC just approved) | MSA, Custody, Fee Schedule, Risk Disclosure, Carbon Derivatives Master Agreement | Yes (generated PDFs with client entity, representative, email; NIHA terms) |
| **deposit_announced** | FUNDING (client announced wire) | Bank Confirmation Letters, Registry Account Overview | No (static PDFs) |
| deposit_on_hold | AML | — | — |
| aml_review_started | AML | — | — |
| trading_activated | CEA | — | Contracts already sent at account_approved |
| welcome_activated, invitation, kyc_rejected, deposit_rejected | various | — | — |

**Optional (not in initial scope):** KYC form PDF (pre-filled with submitted application) at `account_approved` — can be added later if desired.

---

## Document IDs used for attachments

- **account_approved**: `msa`, `custody`, `fee_schedule`, `risk_disclosure`, `derivatives`
- **deposit_announced**: `bank_confirmations`, `registry_overview`

All of the above are client-facing in `DOCUMENT_CATALOG` and available at APPROVED or FUNDING. Generated documents use `generate_*_pdf(...)` with client/entity data; static documents are read from `DOCUMENT_BASE_PATH`.

---

## References

- `backend/app/api/v1/documents.py` — DOCUMENT_CATALOG, download by role
- `backend/app/services/email_service.py` — send_* methods, attachments
- `docs/NDA_TO_EUA_WORKFLOW_SIMULATION.md` — email triggers and flow
- `docs/EMAIL_TEMPLATES_USAGE.md` — which templates are used in code vs NU (not used)
- **Settings → Documents** (admin): lists platform docs from repo **`documents/`** (`.pdf`, `.docx`); each entry has `used` (in catalog or attached to an email) and `email_templates`; unused docs shown as **(NU)**. Backend `GET /api/v1/admin/settings/documents/list` and `GET /api/v1/admin/settings/documents/preview?path=...` (path relative to `documents/`). See `docs/API.md` § Admin — Settings: Documents.
