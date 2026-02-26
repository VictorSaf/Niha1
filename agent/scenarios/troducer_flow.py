# agent/scenarios/troducer_flow.py
"""
E2E Test Plan: TRODUCER → PREINTRODUCER → INTRODUCER onboarding flow.
The agent explores the platform autonomously and reports results.
"""

PROMPT = """
Test the full introducer onboarding flow on the NIHA Carbon Trading Platform.
Execute ALL steps in order. Do not skip any step.

## AUTH RULES (read carefully)
- Auth is in sessionStorage key 'auth-storage' (NOT localStorage)
- Logout: browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
- Login pattern: browser_navigate /login → click "ENTER" button → fill email → fill password → click "CONTINUE" → wait for redirect
- DB queries: shell_run with 'docker compose exec db psql -U niha_user -d niha_carbon -c "SQL"'
- WebSocket warnings in the console are NORMAL — do NOT debug them

## Credentials
- Troducer: tr2@yopmail.com / Troducer123!
- Admin: admin@nihaogroup.com / Admin123!
- Test user: e2e-auto@yopmail.com

---

### Step 0: Cleanup (remove leftover test data before starting)
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "DELETE FROM users WHERE email='e2e-auto@yopmail.com'; DELETE FROM contact_requests WHERE contact_email='e2e-auto@yopmail.com';"

---

### Step 1: Login as Troducer
- browser_navigate to http://localhost:5173/login
- browser_click selector="text:ENTER"   ← REQUIRED: reveals the email/password fields
- browser_fill selector="placeholder:Email" value="tr2@yopmail.com"
- browser_fill selector="placeholder:Password" value="Troducer123!"
- browser_click selector="text:CONTINUE"
- browser_wait_for url_contains="/troducer"
- browser_screenshot label="troducer-dashboard"

### Step 2: Find Referral Code on Screen
- browser_get_text() to read all text on the /troducer page
- Find the referral code shown on screen (short alphanumeric code, e.g. "Riw9MKF!")
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "SELECT referral_code FROM users WHERE email='tr2@yopmail.com';"
- test_assert: description="TC-01: Referral code on screen matches DB", condition=True if screen code == DB code, expected=DB value, actual=screen value

### Step 3: Logout Troducer
- browser_evaluate('() => { sessionStorage.clear(); }')
- browser_navigate to http://localhost:5173/login
- browser_screenshot label="after-troducer-logout"

### Step 4: Get Referral Code from DB for URL
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "SELECT referral_code FROM users WHERE email='tr2@yopmail.com';"
- Read the code from the result
- URL-encode it: replace $ with %24, ! with %21, # with %23, @ with %40

### Step 5: Navigate to Introducer Page with Referral Code
- browser_navigate to http://localhost:5173/introducer?ref=<ENCODED_CODE>
- browser_screenshot label="introducer-landing"
- browser_get_text() to read all text and understand the page

### Step 6: Open Introducer Request Form
- Find the button that opens the contact/request form (NOT the ENTER login button)
- browser_click that button
- browser_screenshot label="introducer-form-open"
- browser_get_text() to see form fields

### Step 7: Fill and Submit Introducer Form
- Fill Entity Name field with "E2E Auto Corp"
- Fill Email field with "e2e-auto@yopmail.com"
- Fill First Name with "Auto"
- Fill Last Name with "Test"
- Fill Position with "QA"
- Click the submit button
- browser_screenshot label="introducer-form-submitted"
- browser_get_text() to read the result
- test_assert: description="TC-02: Introducer form submitted successfully", condition=True if success/confirmation text is visible, expected="Success message visible", actual=page text summary

### Step 8: Verify PREINTRODUCER in DB
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "SELECT email, role, is_active, invitation_token IS NOT NULL as has_token FROM users WHERE email='e2e-auto@yopmail.com';"
- Read the result carefully
- test_assert: description="TC-03a: Role is PREINTRODUCER", condition=True if "PREINTRODUCER" in result, expected="PREINTRODUCER", actual=role value from DB
- test_assert: description="TC-03b: User is not yet active", condition=True if "f" or "false" in is_active column, expected="is_active=false", actual=is_active value
- test_assert: description="TC-03c: Invitation token exists", condition=True if "t" or "true" in has_token column, expected="has_token=true", actual=has_token value

### Step 9: Get Invitation Token from DB
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "SELECT invitation_token FROM users WHERE email='e2e-auto@yopmail.com';"
- Copy the token value from the result

### Step 10: Setup Password via Invitation Link
- browser_navigate to http://localhost:5173/setup-password?token=<TOKEN>
- browser_screenshot label="setup-password-page"
- browser_get_text() to read the form structure
- Find the password input fields
- browser_fill the password field with "AutoTest123!"
- browser_fill the confirm password field with "AutoTest123!"
- Click the submit/continue/save button
- browser_screenshot label="after-password-set"
- browser_get_text() to read the result
- test_assert: description="TC-04: Password setup completed", condition=True if no error message visible and page advanced, expected="No error, page advanced", actual=page text summary

### Step 11: Upload NDA
- browser_get_text() to read what is on screen after password set
- browser_screenshot label="after-password-step"
- Look for NDA upload section or a file input
- browser_evaluate('() => document.querySelector("input[type=file]") ? "found" : "not found"') to detect file input
- If file input exists: browser_fill selector="input[type=file]" value="/Users/victorsafta/work/Niha/backend/uploads/nda/NDA-Niha-signed.pdf"
- Click submit/upload button
- browser_screenshot label="after-nda-upload"
- browser_get_text() to read result
- test_assert: description="TC-05: NDA uploaded", condition=True if success message visible OR no error shown, expected="Upload successful", actual=page text summary

### Step 12: Logout and Login as Admin
- browser_evaluate('() => { sessionStorage.clear(); }')
- browser_navigate to http://localhost:5173/login
- browser_click selector="text:ENTER"   ← REQUIRED: reveals the email/password fields
- browser_fill selector="placeholder:Email" value="admin@nihaogroup.com"
- browser_fill selector="placeholder:Password" value="Admin123!"
- browser_click selector="text:CONTINUE"
- browser_wait_for url_contains="/dashboard"
- browser_screenshot label="admin-dashboard"

### Step 13: Navigate to Onboarding/Introducer Section in Backoffice
- browser_get_text() to read the admin dashboard navigation
- Look for "Onboarding", "Introducers", or similar nav link
- Click on that nav item
- browser_screenshot label="backoffice-onboarding"
- browser_get_text() to read the list

### Step 14: Approve e2e-auto@yopmail.com NDA
- Find the entry for "e2e-auto@yopmail.com" or "E2E Auto Corp" in the list
- browser_get_text() to read what buttons are available (look for approve, review, etc.)
- Click the approve button for that entry
- browser_screenshot label="after-nda-approval"
- browser_get_text() to read the result
- test_assert: description="TC-06: Admin approved NDA for e2e-auto", condition=True if entry is gone from pending list or status changed to approved, expected="Approved or removed from list", actual=page text summary

### Step 15: Final DB Verification
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "SELECT email, role, is_active, nda_signed FROM users WHERE email='e2e-auto@yopmail.com';"
- test_assert: description="TC-07a: Role is INTRODUCER", condition=True if "INTRODUCER" in result and "PREINTRODUCER" not in result, expected="INTRODUCER", actual=role value
- test_assert: description="TC-07b: User is active", condition=True if "t" in is_active column, expected="is_active=true", actual=is_active value
- test_assert: description="TC-07c: NDA is signed", condition=True if "t" in nda_signed column, expected="nda_signed=true", actual=nda_signed value

### Step 16: Cleanup
- shell_run: docker compose exec db psql -U niha_user -d niha_carbon -c "DELETE FROM users WHERE email='e2e-auto@yopmail.com'; DELETE FROM contact_requests WHERE contact_email='e2e-auto@yopmail.com';"

After completing all 16 steps and their assertions, output a summary report:

TC-01: [PASS/FAIL] — Referral code visible on troducer dashboard matches DB
TC-02: [PASS/FAIL] — Introducer request form submission
TC-03: [PASS/FAIL] — DB shows PREINTRODUCER role with invitation token
TC-04: [PASS/FAIL] — Password setup via invitation link
TC-05: [PASS/FAIL] — NDA file upload
TC-06: [PASS/FAIL] — Admin NDA approval in backoffice
TC-07: [PASS/FAIL] — Final DB state: INTRODUCER, active, nda_signed

BUGS FOUND: <list any unexpected behavior>
OVERALL: [PASS/FAIL]
"""
