# agent/scenarios/troducer_flow.py
"""
E2E Test Plan: TRODUCER → PREINTRODUCER → INTRODUCER onboarding flow.
The agent explores the platform autonomously and reports results.
"""

PROMPT = """
# E2E Test Plan: Introducer Onboarding Flow

## Platform
- URL: http://localhost:5173
- Auth: stored in sessionStorage under key 'auth-storage'
- Logout method: browser_evaluate('() => { sessionStorage.clear(); }') then navigate to /login
- DB access: shell_run('docker compose exec db psql -U niha_user -d niha_carbon -c "SQL"')
- Backend logs: shell_run('docker compose logs backend --since 2m 2>&1 | tail -40')

## Test Credentials
- Troducer: tr2@yopmail.com / Troducer123!
- Admin: admin@nihaogroup.com / Admin123!
- New test user to create: e2e-auto@yopmail.com

## Your Job
Run the full onboarding flow from scratch. Explore the UI yourself — take screenshots, read page text, find buttons and fields on your own. Assert every important state change. At the end give me a full report.

## Test Cases

### TC-01: Troducer Login & Referral Code
- Login as tr2@yopmail.com
- Verify you land on the troducer page
- Find and read the referral code displayed on screen
- Cross-check the code with the DB: SELECT referral_code FROM users WHERE email='tr2@yopmail.com'
- ASSERT: code on screen matches DB

### TC-02: New User Submits Introducer Form
- Log out (sessionStorage.clear() + navigate to /login)
- Navigate to the introducer signup page using the referral code from TC-01
- Explore the page — find the form and fill it with:
  - Entity: "E2E Auto Corp"
  - Email: e2e-auto@yopmail.com
  - First name: Auto, Last name: Test, Position: QA
- Submit the form
- ASSERT: success confirmation is shown

### TC-03: Verify PREINTRODUCER Created
- Query DB: SELECT email, role, is_active, invitation_token IS NOT NULL as has_token FROM users WHERE email='e2e-auto@yopmail.com'
- ASSERT: role = PREINTRODUCER
- ASSERT: is_active = false
- ASSERT: has_token = true (invitation was sent)

### TC-04: Setup Password via Invitation Link
- Get invitation token from DB: SELECT invitation_token FROM users WHERE email='e2e-auto@yopmail.com'
- Navigate to /setup-password?token=<TOKEN>
- Explore the page — find and fill password fields with: AutoTest123!
- Submit the password step
- ASSERT: page advances (NDA upload step appears or success indicator)

### TC-05: NDA Upload
- On the setup page, find the NDA upload area
- Upload file: /Users/victorsafta/work/Niha/backend/uploads/nda/NDA-Niha-signed.pdf
- Submit/complete the NDA upload
- ASSERT: success message shown

### TC-06: Admin Approves in Backoffice
- Log out, login as admin@nihaogroup.com
- Navigate to the backoffice onboarding/introducer section
- Find the entry for "E2E Auto Corp" / e2e-auto@yopmail.com
- Click Approve
- ASSERT: entry disappears from the pending list

### TC-07: Final DB Verification
- Query DB: SELECT email, role, is_active, nda_signed FROM users WHERE email='e2e-auto@yopmail.com'
- ASSERT: role = INTRODUCER
- ASSERT: is_active = true
- ASSERT: nda_signed = true

## Cleanup
After all test cases: shell_run('docker compose exec db psql -U niha_user -d niha_carbon -c "DELETE FROM users WHERE email=\'e2e-auto@yopmail.com\'; DELETE FROM contact_requests WHERE contact_email=\'e2e-auto@yopmail.com\';"')

## Final Report
At the end, give me:
1. PASS/FAIL for each TC-01 through TC-07
2. Any bugs or unexpected behavior observed
3. Screenshots taken and what they show
4. Overall verdict: PASS or FAIL
"""
