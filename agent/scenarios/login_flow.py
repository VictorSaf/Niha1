# agent/scenarios/login_flow.py
"""Scenario: Login flow for all roles."""

PROMPT = """
Test the login flow for multiple user roles on the NIHA platform.

## IMPORTANT AUTH FACTS (read before starting)
- Auth state is stored in SESSIONSTORAGE (not localStorage) under key 'auth-storage'
- Checking token: browser_evaluate('() => { const s = sessionStorage.getItem("auth-storage"); return s ? JSON.parse(s).state.token : "NO TOKEN"; }')
- Logging out properly: browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
  After sessionStorage.clear() + navigate, the React app reloads fresh with no auth → stays on /login
- Do NOT use localStorage.clear() — auth is NOT in localStorage

## Steps:

### 1. Admin Login
- Navigate to http://localhost:5173/login
- Click ENTER button
- Fill email: admin@nihaogroup.com
- Fill password: Admin123!
- Click CONTINUE
- Call browser_wait_for(url_contains="/dashboard")
- Take screenshot "admin-dashboard"
- Assert: URL contains /dashboard
- Check token: browser_evaluate('() => { const s = sessionStorage.getItem("auth-storage"); return s ? "TOKEN_FOUND" : "NO_TOKEN"; }')
- Assert: result is TOKEN_FOUND (sessionStorage has auth data)

### 2. Logout Admin
- Call browser_evaluate('() => { sessionStorage.clear(); }')
- Call browser_navigate("http://localhost:5173/login")
- Assert: URL is http://localhost:5173/login (not redirected to dashboard)
- Take screenshot "after-logout-login-page"

### 3. Troducer Login
- Click ENTER button
- Fill email: tr2@yopmail.com
- Fill password: Troducer123!
- Click CONTINUE
- Call browser_wait_for(url_contains="/troducer")
- Take screenshot "troducer-page"
- Assert: URL contains /troducer
- Assert: Page text contains "Referral Code" (use browser_get_text())

### 4. Wrong Password
- Call browser_evaluate('() => { sessionStorage.clear(); }')
- Call browser_navigate("http://localhost:5173/login")
- Click ENTER
- Fill email: admin@nihaogroup.com
- Fill password: WrongPassword99!
- Click CONTINUE
- Wait 2 seconds: browser_wait_for(selector=".text-red", timeout_ms=5000) or check page text
- Take screenshot "login-error-wrong-password"
- Assert: URL is still http://localhost:5173/login (no redirect happened)
- Assert: Page text contains "Invalid" or "incorrect" or "wrong"

### 5. Check DB for user counts
- shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role;\\"")
- Assert: At least one admin user exists (ADMIN role count > 0)
- Assert: At least one troducer exists (TRODUCER role count > 0)

Report PASS/FAIL for all 5 steps.
"""
