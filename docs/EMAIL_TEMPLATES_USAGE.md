# Email templates: used in code vs not used (NU)

Lista template-urilor de email: care sunt trimise din cod (**Used**) și care nu sunt apelate în niciun flux (**NU**). În Settings (Backoffice) template-urile nefolosite sunt afișate cu sufixul ** (NU)**.

## Template-uri folosite (Used)

| Template | Apelat din |
|----------|------------|
| account_approved.html | backoffice.py — Approve KYC |
| account_funded.html | backoffice.py — după fund user |
| admin_overdue_settlement.html | settlement_processor.py — alert admin |
| aml_review_started.html | backoffice.py — Confirm deposit (path backoffice) |
| cea_settlement_pending.html | role_transitions.py — CEA → CEA_SETTLE |
| contact_followup.html | contact.py — după contact request |
| deposit_announced.html | deposits.py — announce_deposit |
| deposit_on_hold.html | deposits.py — confirm deposit (path deposits API) |
| deposit_rejected.html | deposits.py, backoffice.py — reject deposit |
| eua_access_granted.html | role_transitions.py — EUA_SETTLE → EUA |
| eua_settlement_pending.html | role_transitions.py — SWAP → EUA_SETTLE |
| introducer_approved.html | admin.py — Approve NDA introducer |
| introducer_nda_invitation.html | contact.py, admin.py — NDA + setup parolă introducer |
| invitation.html | admin.py — Create user (invitation) |
| kyc_rejected.html | backoffice.py — Reject KYC |
| magic_link.html | auth.py — magic link login |
| pre_nda_approved.html | admin.py — NDA aprobat (buyer PRE_NDA) |
| pre_nda_invitation.html | admin.py — NDA + setup parolă buyer |
| referral_invitation.html | introducer.py — invitație referral |
| settlement_completed.html | settlement_service.py |
| settlement_created.html | settlement_service.py |
| settlement_failed.html | settlement_service.py |
| settlement_status_update.html | settlement_processor.py, settlement_service.py |
| swap_access_granted.html | role_transitions.py — CEA_SETTLE → SWAP |
| swap_match.html | swaps.py — swap match notification |
| test_email.html | admin.py — endpoint test email |
| trade_confirmation.html | cash_market.py — după trade |
| trading_activated.html | deposits.py — după clear (AML → CEA) |
| troducer_welcome.html | admin.py — Create user TRODUCER cu parolă |
| welcome_activated.html | auth.py — după setare parolă (activare cont) |
| withdrawal_approved.html | withdrawals.py |
| withdrawal_completed.html | withdrawals.py |
| withdrawal_rejected.html | withdrawals.py |
| withdrawal_requested.html | withdrawals.py |

## Template-uri nefolosite (NU)

| Template | Motiv |
|----------|--------|
| **deposit_cleared.html** | Metoda `send_deposit_cleared` există în `email_service.py` dar **nu este apelată** în niciun flux. După clear deposit se trimite doar **trading_activated** către userii AML→CEA (deposits.py). Template-ul ar putea fi folosit dacă se dorește un email separat „Fonduri disponibile” în plus față de trading_activated. |

## User journey: template lipsă?

**Nu lipsește niciun template** din user journey. Toate etapele (contact → NDA → KYC → APPROVED → FUNDING → AML → CEA → … → EUA) au emailuri definite și trimise. Singura excepție este **deposit_cleared**, care există ca template dar nu e folosit; fluxul actual folosește doar **trading_activated** după clear.

## API

**GET /api/v1/admin/settings/mail/templates** (Admin only)

Returns the list of email template filenames with a `used` flag (whether the template is sent from application code).

- **Response**: `200 OK`
- **Body**: `{ "templates": [ { "name": "account_approved.html", "used": true }, { "name": "deposit_cleared.html", "used": false }, ... ] }`

**GET /api/v1/admin/settings/mail/preview/{template_name}** (Admin only)

Renders the template with sample data and returns HTML for the Settings preview iframe.

- **Response**: `200 OK` (HTML) or `404` if template not found.

## Frontend (Settings → Mail & Authentication)

- **Email Templates** card: dropdown lists all templates; unused ones show **(NU)**. Preview button opens sample render in an iframe.
- If the templates list fails to load, an in-card error message is shown (amber, non-blocking); dropdown and Preview are hidden until the next successful load.
- When the list is updated (e.g. after a failed then successful load), the selected template is reset to the first item if the current selection is no longer in the list.

## Referințe

- `backend/app/services/email_service.py` — `USED_EMAIL_TEMPLATES`, `UNUSED_EMAIL_TEMPLATES`, `list_templates_with_usage()`
- `backend/tests/test_email_lifecycle.py` — `test_list_templates_with_usage_deposit_cleared_not_used`, `test_list_templates_with_usage_every_template_classified` (detectează drift între template-uri și constante)
- `backend/app/api/v1/admin.py` — `GET /admin/settings/mail/templates`, `GET /admin/settings/mail/preview/{template_name}`
- `docs/NDA_TO_EUA_WORKFLOW_SIMULATION.md` — flux NDA → EUA și emailuri per tranziție
- `docs/TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md` — flux Troducer/Introducer și emailuri
