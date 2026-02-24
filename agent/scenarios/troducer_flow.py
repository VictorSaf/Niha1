# agent/scenarios/troducer_flow.py
"""
Scenario: TRODUCER -> PREINTRODUCER -> INTRODUCER full flow
Tests the complete introducer onboarding path via referral code.
"""

PROMPT = """
Test the TRODUCER -> PREINTRODUCER -> INTRODUCER onboarding flow on the NIHA platform.

## Steps to test:

### 1. Troducer Login
- Navigate to http://localhost:5173/login
- Click ENTER button
- Fill email: tr2@yopmail.com, password: Troducer123!
- Click CONTINUE
- Assert: URL redirects to /troducer
- Assert: Referral code is visible on the page (non-empty string)
- Take screenshot labeled "troducer-dashboard"

### 2. Get Referral Code
- Use browser_get_text on the referral code element (it's a large monospace text in the center)
- Extract the code value
- Use shell_run to verify the code in DB:
  shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT referral_code FROM users WHERE email='tr2@yopmail.com';\\"")
- Assert: DB code matches what's shown on screen

### 3. New User Visits Referral Link
- Use browser_evaluate to clear localStorage: "() => { localStorage.clear(); }"
- Navigate to http://localhost:5173/introducer?ref=<CODE_FROM_STEP_2>
  (URL-encode $ as %24 in the code)
- Click NDA button
- Assert: Form appears WITHOUT an NDA file upload field
- Assert: Form shows message about receiving NDA via email
- Take screenshot labeled "introducer-form-no-upload"

### 4. Fill and Submit Form
- Fill entity name: "Test Corp E2E"
- Fill email: "e2e-test-agent@yopmail.com"
- Fill first name: "Agent"
- Fill last name: "Test"
- Fill position: "CTO"
- Click SUBMIT
- Assert: Success page appears ("Request Submitted")
- Take screenshot labeled "form-submitted-success"

### 5. Verify PREINTRODUCER Created in DB
- shell_run to check user was created:
  shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email, role, is_active, invitation_token IS NOT NULL as has_token FROM users WHERE email='e2e-test-agent@yopmail.com';\\"")
- Assert: role = PREINTRODUCER
- Assert: is_active = false (not yet active)
- Assert: has_token = true (invitation email was sent)

### 6. Get Invitation Token + Simulate Setup Link
- shell_run to get token:
  shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT invitation_token FROM users WHERE email='e2e-test-agent@yopmail.com';\\"")
- Navigate to http://localhost:5173/setup-password?token=<TOKEN>
- Assert: Welcome message shows "Agent" name
- Assert: Email field is pre-filled and disabled

### 7. Set Password
- Fill password field with "AgentTest123!"
- Fill confirm password with "AgentTest123!"
- Assert: Password match indicator shows "Passwords match"
- Click "Set Password & Continue"
- Assert: Page advances to NDA upload step (Step 2 indicator)
- Take screenshot labeled "password-set-step2"

### 8. Upload NDA
- Click the NDA drop zone
- Upload file: /Users/victorsafta/work/Niha/backend/uploads/nda/NDA-Niha-signed.pdf
- Assert: File name appears in the drop zone
- Click "Upload NDA & Complete Setup"
- Assert: "NDA Uploaded Successfully" message appears
- Take screenshot labeled "nda-uploaded-success"

### 9. Admin Reviews in Backoffice
- Clear localStorage and navigate to /login
- Login as admin: admin@nihaogroup.com / Admin123!
- Navigate to http://localhost:5173/backoffice/onboarding/introducer
- Assert: "Test Corp E2E" / "Agent Test" entry appears with "NDA Uploaded" badge
- Assert: "Approve NDA" button is visible for this entry
- Take screenshot labeled "backoffice-introducer-list"

### 10. Admin Approves NDA
- Click "Approve NDA" button for "Test Corp E2E"
- Assert: Entry disappears from the list (badge count decreases)
- shell_run to verify DB:
  shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email, role, is_active, nda_signed FROM users WHERE email='e2e-test-agent@yopmail.com';\\"")
- Assert: role = INTRODUCER
- Assert: is_active = true
- Assert: nda_signed = true
- Take screenshot labeled "approved-user-gone-from-list"

## Cleanup after test
shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"DELETE FROM users WHERE email='e2e-test-agent@yopmail.com'; DELETE FROM contact_requests WHERE contact_email='e2e-test-agent@yopmail.com';\\"")

Report overall PASS/FAIL.
"""
