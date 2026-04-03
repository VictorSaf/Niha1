# Code review — Feature 0072: Eliminare rol TRODUCER

**Plan:** [`docs/features/0072_PLAN.md`](0072_PLAN.md)  
**Review criteria:** [`docs/commands/code_review.md`](docs/commands/code_review.md)

---

## Summary

**Plan 0072 is implemented.** The `TRODUCER` role is removed from application enums, APIs, referral `validate-code` contract (`preintroducer` | `introducer` only), admin flows (Send NDA → **PREINTRODUCER**; approve-nda filters **PREINTRODUCER** / **PRE_NDA**), email (`troducer_welcome` removed), frontend routes (`/troducer` and `TroducerPage` removed), and tests. Data migrations `2026_04_02_troducer_preintro` (row update) and `2026_04_03_userrole_no_troducer` (drop `TRODUCER` from PostgreSQL `userrole` enum) complete the removal. SSOT and cross-docs were updated; `docs/TRODUCER_WORKFLOW_AND_EMAIL_ANALYSIS.md` remains as a pointer for old links.

**Verification (2026-04-02):** `docker compose exec backend pytest --tb=short -q` — 55 passed, 15 skipped; `cd frontend && npx tsc --noEmit && npm test -- --run` — 255 passed (28 files).

---

## Confirmation: plan fully implemented?

**Yes**, aligned with plan § Fișiere principale and replacement rules.

| Area | Plan | Status |
|------|------|--------|
| DB migration | `UPDATE users …` + enum without `TRODUCER` | `2026_04_02_troducer_preintro.py`, `2026_04_03_userrole_no_troducer.py` |
| `UserRole.TRODUCER` | Removed from Python/API usage | Absent from `models.py` / `schemas.py` usage paths |
| `validate-code` | No `type: troducer` | `referral_codes.py` maps only PREINTRODUCER / INTRODUCER |
| Admin Send NDA | PREINTRODUCER | `send_introducer_nda` sets `PREINTRODUCER` |
| Frontend | No `/troducer`, no Troducer UI | Route and page removed; Header / CommandPalette / CreateUser use PREINTRODUCER / INTRODUCER |
| Tests | PREINTRODUCER referral in 0071 tests | `test_contact_0071.py` uses `_create_preintroducer_with_referral_code`, `type == preintroducer` |
| Docs / SSOT | app_truth, API, email mapping | Updated; historical doc is pointer |

---

## Issues (by severity)

### Critical

*None.*

### Major

*None.*

### Minor

1. **`validate-code` + INTRODUCER** — `backend/tests/test_contact_0071.py` asserts `type: preintroducer` for a PREINTRODUCER referral holder. There is no parallel test that a valid code owned by an **INTRODUCER** returns `type: introducer`. Mapping in `referral_codes.py` covers both; adding one small test would lock the dual contract.

**Resolved (2026-04):**

1. **PostgreSQL enum** — `2026_04_03_userrole_no_troducer` recreates `userrole` without the `TRODUCER` label after data migration.

2. **Alembic revision length** — Revision IDs must be ≤32 characters (`alembic_version.version_num`). Migrations `2026_04_02_troducer_preintro` and `2026_04_03_userrole_no_troducer` replace longer names that failed to apply.

3. **README.md** — Login NDA flow wording uses **PREINTRODUCER** (not TRODUCER).

---

## Specific file references (implementation touchpoints)

| Layer | Files / behaviour |
|------|-------------------|
| Migration | `2026_04_02_troducer_preintro.py`, `2026_04_03_userrole_no_troducer.py` |
| Referral | `backend/app/services/referral_codes.py` — `preintroducer` \| `introducer` |
| Contact | `backend/app/api/v1/contact.py` — duplicate check PREINTRODUCER/INTRODUCER; `introducer-request` requires `preintroducer`; upload-nda PREINTRODUCER/INTRODUCER/PRE_NDA |
| Admin | `backend/app/api/v1/admin.py` — `send_introducer_nda` → PREINTRODUCER; `approve_introducer_nda` without TRODUCER |
| Fees | `backend/app/api/v1/admin_fees.py` — INTRODUCER, PREINTRODUCER only |
| Email | `backend/app/services/email_service.py` — PREINTRODUCER/INTRODUCER dashboard URLs; no troducer welcome |
| Frontend | `App.tsx`, `redirect.ts`, `types`, `LoginPage`, `IntroducerPage`, `api.ts` `validateCode`, tests |
| Tests | `backend/tests/test_contact_0071.py`, `frontend/src/utils/__tests__/redirect.test.ts`, `effectiveRole.test.ts` |

---

## Recommendations

1. After deploy, run `alembic upgrade head` so legacy `TRODUCER` rows migrate before new app code serves traffic.

2. Optional: `rg 'TRODUCER|troducer'` on release branches to catch doc or copy drift (expect hits in historical migrations, pointer doc, migration filename in CLAUDE.md).

---

## Testing and quality

- Backend and frontend test suites pass with the new contract.
- Edge cases to remain aware of: duplicate-email **409** on `introducer-nda-request`, **503** when NDA PDF generation fails, validate-code rate limits — unchanged in intent, now without TRODUCER.

---

## Security and edge cases

- No new exposure identified: admin-only create paths and referral consumption remain role-scoped; removed role reduces surface area.

---

## UI/UX and interface analysis

Per **`docs/commands/code_review.md`** and **`docs/commands/interface.md`**:

- **Navigation & roles:** Troducer-only routes and palette entries are removed. **PREINTRODUCER** (“Referral Code” → `/preintroducer`) and **INTRODUCER** (“Introducer Portal” / dashboard) match **`app_truth.md`** and preserve theme-aware Tailwind (`navy-*`, `emerald-*`).
- **Forms / login flow:** `LoginPage` / `IntroducerPage` changes are limited to the `validateCode` union (`preintroducer` | `introducer`); no broad restyle. CLAUDE.md notes LoginPage is no longer globally frozen for drive-by redesigns; this feature used minimal edits only.
- **Design tokens:** No new `slate-*`/`gray-*` or hex colors introduced for 0072; existing `design-tokens.css` / Tailwind patterns retained.
- **Accessibility / states:** No new interactive widgets; redirect and role-gated routes behave as before for PREINTRODUCER/INTRODUCER.

**Optional improvement:** Add a backend test for `POST /contact/validate-code` with an INTRODUCER-owned code → `type: introducer` (see Minor above).

---

## Conclusion

**Implementation quality:** Delivered — TRODUCER is fully removed from the application layer; data migration handles existing users; documentation and tests align with behaviour.
