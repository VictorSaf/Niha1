# 0071 – Code Review: TRODUCER code flow (Login → NDA → code entry → introducer NDA invitation → INTRODUCER)

## Summary of implementation quality

The feature described in **0071_PLAN.md** is **correctly implemented**. The end-to-end flow (TRODUCER shares code → recipient enters code on Login → submits introducer form without NDA → receives email with NDA attached → follows setup-password link → uploads NDA → admin approves → INTRODUCER) is in place and aligned with the plan and with `app_truth.md` §8 (Referral Code Access System, PREINTRODUCER, INTRODUCER).

- **Backend**: `validate_code`, `create_introducer_nda_request`, **INTRODUCER** user creation (not PREINTRODUCER) when cod TRODUCER + no NDA, NDA generation, `send_introducer_nda_invitation` with attachments, and `approve_introducer_nda` behave as specified.
- **Frontend**: Login page modes (`nda` → `code-entry` → `introducer-form`), `validateCode` / `submitIntroducerNDARequest` with `referral_code`; SetupPasswordPage NDA step remains for PREINTRODUCER with `!ndaSigned` (other flows).
- **Data flow**: Referral code is sent as `referral_code`; backend consumes it and creates User + sends email only when `request_flow == "introducer"`, no NDA file, and valid referral. No snake_case/camelCase or nesting mismatches found for this flow.

---

## Plan implementation confirmation

| Verification point | Status | Notes |
|--------------------|--------|--------|
| LoginPage `introducer-form` sends `referral_code` in `submitIntroducerNDARequest` | ✅ | `referralCode.trim()` passed as `referral_code` (LoginPage.tsx ~298). |
| `introducer-nda-request` accepts empty `position` | ✅ | Backend `position: str = Form(...)`; LoginPage sends `position: ''`. |
| `introducer_nda_invitation` has NDA attached | ✅ | `get_document_bytes("nda", ...)` → `nda_attachments` → `send_introducer_nda_invitation(..., nda_attachments=...)` (contact.py 516–527). |
| SetupPasswordPage shows NDA upload for PREINTRODUCER with `!ndaSigned` | ✅ | `user.role === 'PREINTRODUCER' && !user.ndaSigned` → `setStep('nda')` (SetupPasswordPage.tsx 96–98). Login cod TRODUCER path creates INTRODUCER with nda_signed=true, so no NDA step. |

---

## Issues found

### Critical

1. **User created without setup email when NDA PDF generation fails** — **FIXED**  
   - **Where**: `backend/app/api/v1/contact.py` (lines 467–527). The flow previously created the INTRODUCER user first, then called `get_document_bytes("nda", ...)`. If that failed, the user was left in the DB without ever receiving the setup email.  
   - **Fix**: NDA PDF is now generated **before** creating the user. If `get_document_bytes` fails, no user is created and the endpoint returns **503** with detail `"Unable to prepare invitation. Please try again later."` so the client can retry. `HTTPException` is re-raised so the 503 is returned to the client. Test coverage: `test_introducer_nda_request_503_when_nda_pdf_fails` in `tests/test_contact_0071.py`.

### Major

None.

### Minor

1. **No automated tests for 0071 flow** — **FIXED**  
   - **Where**: Backend had no tests for `POST /contact/validate-code` or for the `create_introducer_nda_request` path.  
   - **Fix**: Added `tests/test_contact_0071.py` with: `test_validate_code_valid`, `test_validate_code_invalid`, `test_validate_code_rate_limit_429`, `test_introducer_nda_request_creates_introducer_and_sends_email` (mocks `get_document_bytes` and `send_introducer_nda_invitation`). Updated to expect INTRODUCER (not PREINTRODUCER) and nda_signed=True for this flow.

2. **Rate limit fail-open**  
   - **Where**: `contact.py` `_check_rate_limit` (54–70): on Redis failure (except `HTTPException`), the code logs and allows the request.  
   - **Note**: Documented as intentional (“Redis unavailable — allow the request”). Acceptable for resilience; no change required unless product decides otherwise.

3. **Code entry input length** — **FIXED**  
   - **Where**: `LoginPage.tsx` code-entry input had `maxLength={16}`; referral codes are 8 characters.  
   - **Fix**: Set `maxLength={8}` so the input matches the backend code length and avoids user confusion.

4. **Frozen files extended**  
   - **Where**: `LoginPage.tsx` and `SetupPasswordPage.tsx` are listed in `app_truth.md` §10 (Frozen files). This feature adds modes and handlers to both.  
   - **Note**: The plan explicitly lists these files as part of the implementation; treating this as an approved functionality change. Only bug fixes and security fixes should be applied to frozen files without explicit approval.

---

## Recommendations for improvements

- **Tests**: Done — added `tests/test_contact_0071.py` (validate_code valid/invalid/429, introducer-nda-request → PREINTRODUCER + NDA email).
- **Documentation**: Done — noted that the Login “I have a code” (cod TRODUCER) → introducer form submit (no NDA) triggers **INTRODUCER** creation and `introducer_nda_invitation` with NDA attached (app_truth.md §8).

---

## Error handling and edge cases

- **Backend**: Invalid referral code → `consume_referral_code` returns `None` → no User created, no NDA email; ContactRequest still created (generic followup only). Exception path for user creation/email is try/except with non-blocking behaviour and logging (contact.py 446–554).
- **Frontend**: Code validation 429 → user-facing “Too many attempts. Please wait 10 minutes and try again.” (LoginPage.tsx 259–263). Submit failure → generic “Unable to process request. Please try again.” (303–304). Appropriate for a frozen Login page.

---

## Security and best practices

- Code validation is rate-limited (5 per IP per 10 min) via Redis; 429 returned when exceeded.
- Referral code is consumed only on form submit (not on validate), preventing one-time code use on validation.
- NDA file type/size validated (PDF, 10MB); email uses configured mail config and base URL for setup link.
- No sensitive data exposed in responses; error messages are generic.

---

## UI/UX and interface (feature touches frozen UI)

- **Scope**: This feature adds behaviour and copy to **LoginPage** and **SetupPasswordPage** (modes, code entry, introducer form, NDA step). Both are frozen per `app_truth.md` §10; only bug fixes and security fixes are allowed without explicit approval; this implementation is treated as an approved functionality change per the plan.
- **Design**: No new standalone UI components were introduced; existing patterns (form fields, buttons, error messages) are used. No hard-coded colors or design-token violations were introduced in the changed code paths.
- **Accessibility / responsiveness**: Not re-audited for the frozen pages; existing behaviour preserved.

---

## Conclusion

- **Plan**: Fully implemented; all verification points from 0071_PLAN.md are satisfied.  
- **Quality**: Implementation is consistent with the codebase, app_truth, and referral/INTRODUCER flow.  
- **Change (post-review)**: Login NDA + cod TRODUCER + introducer form (no NDA) now creates **INTRODUCER** user with `nda_signed=True` and sends email with NDA attached (no PREINTRODUCER step; no admin approval needed for this path).  
- **Action items**: Addressed — tests in `tests/test_contact_0071.py` updated to expect INTRODUCER; documentation updated.

---

## Follow-up fixes (post code-review)

After a second pass (code-reviewer subagent and manual fixes), the following were implemented:

| Issue | Fix |
|-------|-----|
| **SetupPasswordPage token key** (Major) | Use `res.accessToken ?? res.access_token ?? ''` and optional return type in `api.ts` so auth store receives the token whether API returns snake_case or camelCase. |
| **Duplicate introducer submission** (Minor) | In `create_introducer_nda_request`, when `request_flow=introducer`, no NDA file, and valid referral: if a user with that email already has role PREINTRODUCER/INTRODUCER/TRODUCER, return **409** and do not create a second ContactRequest. LoginPage shows 409 `detail` when present. |
| **Redis rate-limit fail-open** (Minor) | Documented in `app_truth.md` §8 (Referral Code): "if Redis is unavailable the request is allowed — fail-open for resilience". |
| **PREINTRODUCER login before approval** (Recommendation) | In `password_login`, reject with **403** when `user.role == PREINTRODUCER` and `not user.nda_signed`; message: "Your NDA is pending approval. You cannot log in until an administrator approves your NDA." Documented in `app_truth.md` §8. |

- **Tests**: Added `test_introducer_nda_request_duplicate_email_409`; existing 0071 tests use unique emails per run.  
- **Build/tests**: `npx tsc --noEmit` (frontend), `pytest` (backend), `ruff check` (backend) pass.
