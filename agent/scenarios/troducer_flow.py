# agent/scenarios/troducer_flow.py
"""
E2E Test Plan: TRODUCER → PREINTRODUCER → INTRODUCER onboarding flow.
The agent explores the platform autonomously and reports results.
"""

PROMPT = """
# E2E Test Plan: Introducer Onboarding Flow

## Platform
- Frontend: http://localhost:5173
- Auth is stored in sessionStorage (NOT localStorage) under key 'auth-storage'
- To logout: browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
- DB queries: shell_run('docker compose exec db psql -U niha_user -d niha_carbon -c "YOUR SQL"')
- Backend logs: shell_run('docker compose logs backend --since 2m 2>&1 | tail -40')

## Credentials
- Troducer: tr2@yopmail.com / Troducer123!
- Admin: admin@nihaogroup.com / Admin123!
- Test user to create: e2e-auto@yopmail.com

## Instructions
Explore the UI yourself. Take screenshots at every step. Read page text with browser_get_text() to find what elements exist before clicking. Do not assume selectors — discover them. Call test_assert() for every verification. At the very end, produce a structured report.

---

## TC-01: Troducer Login & Referral Code
1. Navigate to http://localhost:5173/login
2. Log in as tr2@yopmail.com / Troducer123!
3. Take a screenshot of the page you land on
4. Read the page text — find the referral code displayed on screen
5. Confirm the code in DB: SELECT referral_code FROM users WHERE email='tr2@yopmail.com'
6. test_assert: code visible on screen matches DB value

## TC-02: New User Submits Introducer Application
1. Logout (sessionStorage.clear() + navigate to http://localhost:5173/login)
2. Get the referral code from DB: SELECT referral_code FROM users WHERE email='tr2@yopmail.com'
3. Navigate to http://localhost:5173/introducer?ref=<CODE> (URL-encode special chars: $ → %24, ! → %21)
4. Take screenshot, read page text to understand what is on screen
5. Find and click the button that opens the introducer request form (not the login/enter button)
6. Fill the form: Entity Name="E2E Auto Corp", Email="e2e-auto@yopmail.com", First Name="Auto", Last Name="Test", Position="QA"
7. Submit the form
8. Take screenshot of the result
9. test_assert: success/confirmation message is visible

## TC-03: DB State — PREINTRODUCER Created
1. Run: SELECT email, role, is_active, invitation_token IS NOT NULL as has_token FROM users WHERE email='e2e-auto@yopmail.com'
2. test_assert: role = PREINTRODUCER
3. test_assert: is_active = false
4. test_assert: has_token = true

## TC-04: New User Sets Password via Invitation Link
1. Get token: SELECT invitation_token FROM users WHERE email='e2e-auto@yopmail.com'
2. Navigate to http://localhost:5173/setup-password?token=<TOKEN>
3. Take screenshot, read page to understand the form structure
4. Fill password fields with AutoTest123!
5. Submit
6. Take screenshot of result
7. test_assert: page advances past the password step (no error shown)

## TC-05: NDA Upload
1. Still on the setup flow — find the NDA upload section
2. Upload the file at: /Users/victorsafta/work/Niha/backend/uploads/nda/NDA-Niha-signed.pdf
3. Submit/confirm the upload
4. Take screenshot
5. test_assert: success or confirmation message visible

## TC-06: Admin Approves NDA in Backoffice
1. Logout, navigate to http://localhost:5173/login, login as admin@nihaogroup.com / Admin123!
2. Navigate to the backoffice introducer onboarding section (explore the nav to find it)
3. Take screenshot of the list
4. Find the entry for e2e-auto@yopmail.com or "E2E Auto Corp"
5. Click the approve button for that entry
6. Take screenshot after approval
7. test_assert: the entry is no longer visible in the pending list

## TC-07: Final DB Verification
1. Run: SELECT email, role, is_active, nda_signed FROM users WHERE email='e2e-auto@yopmail.com'
2. test_assert: role = INTRODUCER
3. test_assert: is_active = true
4. test_assert: nda_signed = true

## Cleanup
shell_run('docker compose exec db psql -U niha_user -d niha_carbon -c "DELETE FROM users WHERE email=\'e2e-auto@yopmail.com\'; DELETE FROM contact_requests WHERE contact_email=\'e2e-auto@yopmail.com\';"')

## Final Report (required)
After cleanup, output a structured summary:

TC-01: [PASS/FAIL] — <one line description>
TC-02: [PASS/FAIL] — <one line description>
TC-03: [PASS/FAIL] — <one line description>
TC-04: [PASS/FAIL] — <one line description>
TC-05: [PASS/FAIL] — <one line description>
TC-06: [PASS/FAIL] — <one line description>
TC-07: [PASS/FAIL] — <one line description>

BUGS FOUND: <list any unexpected behavior>
OVERALL: [PASS/FAIL]
"""
