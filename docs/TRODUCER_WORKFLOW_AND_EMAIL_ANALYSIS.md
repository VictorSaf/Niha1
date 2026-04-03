<!-- [STALE: 2026-04-03] Rolul TRODUCER eliminat în feature 0072. Fișier pointer. Sursa de adevăr: app_truth.md §PREINTRODUCER. Vezi docs/STALE_CONTENT.md. -->

# Introducer referral workflow (replaces TRODUCER analysis)

The **TRODUCER** user role was **removed** in feature **0072** (2026-04). Onboarding for introducers pending NDA approval uses **PREINTRODUCER** (referral code, `nda_signed=false`) and the same email/approval path as before, without a separate role or `/troducer` route.

**Authoritative behaviour:** see **`app_truth.md`** (Referral Code Access System, PREINTRODUCER, INTRODUCER, duplicate check on `POST /contact/introducer-nda-request`).

**Emails and documents:** **`docs/DOCUMENT_EMAIL_MAPPING.md`**, **`docs/EMAIL_TEMPLATES_USAGE.md`**.

**Buyer vs introducer NDA:** **`docs/NDA_TO_EUA_WORKFLOW_SIMULATION.md`**.

The historical long-form Troducer walkthrough is superseded by the above; keep this file as a pointer so old links remain valid.
