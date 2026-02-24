# agent/scenarios/login_flow.py
"""Scenario: Login flow for all roles."""

PROMPT = """
Test the login flow for multiple user roles on the NIHA platform.

## Steps:

### 1. Admin Login
- Navigate to http://localhost:5173/login, click ENTER
- Fill admin@nihaogroup.com / Admin123!, click CONTINUE
- Assert: Redirects to /dashboard
- Assert: Nav shows "Onboarding" link (admin-only)
- Take screenshot "admin-dashboard"
- browser_evaluate: "() => localStorage.getItem('auth-storage')"
- Assert: token is present in localStorage

### 2. Logout Admin
- browser_evaluate: "() => { localStorage.clear(); }"
- Navigate to /login
- Assert: ENTER and NDA buttons visible (not logged in)

### 3. Troducer Login
- Click ENTER, fill tr2@yopmail.com / Troducer123!, CONTINUE
- Assert: Redirects to /troducer
- Assert: Page shows "Your Referral Code"
- Assert: Nav shows "Troducer Code" link
- Take screenshot "troducer-page"

### 4. Wrong Password
- Clear localStorage, navigate to /login, click ENTER
- Fill admin@nihaogroup.com / WrongPassword99!
- Click CONTINUE
- Assert: Error message "Invalid email or password" appears
- Assert: URL remains /login
- Take screenshot "login-error-wrong-password"

### 5. Inactive User
- shell_run to get an NDA-role user: shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email FROM users WHERE role='NDA' LIMIT 1;\\"")
- Try logging in as that user with any password
- Assert: Login fails (user not active or no password set)

Report PASS/FAIL for all 5 steps.
"""
