# agent/scenarios/login_flow.py
"""Scenario: Login flow for all roles."""

PROMPT = """
Test the login flow for multiple user roles on the NIHA platform.

## AUTH RULES (read carefully before starting)
- Auth state is in sessionStorage key 'auth-storage' (NOT localStorage)
- To logout: call browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
- WebSocket warnings in the browser console are NORMAL — do NOT debug them

## Test Steps

### Step 1: Admin Login
- browser_navigate to http://localhost:5173/login
- browser_click selector="text:ENTER"
- browser_fill selector="placeholder:Email" value="admin@nihaogroup.com"
- browser_fill selector="placeholder:Password" value="Admin123!"
- browser_click selector="text:CONTINUE"
- browser_wait_for url_contains="/dashboard"
- browser_screenshot label="admin-dashboard"
- Get current URL with browser_evaluate('() => window.location.href')
- Call test_assert: description="Admin login redirects to /dashboard", condition=True if the URL result contains "/dashboard" else False, expected="/dashboard in URL", actual=the URL you got
- Call browser_evaluate('() => { const s = sessionStorage.getItem("auth-storage"); return s ? "TOKEN_FOUND" : "NO_TOKEN"; }')
- Call test_assert: description="Auth token present in sessionStorage after admin login", condition=True if result is "TOKEN_FOUND" else False, expected="TOKEN_FOUND", actual=the result you got

### Step 2: Logout Admin
- Call browser_evaluate('() => { sessionStorage.clear(); }')
- browser_navigate to http://localhost:5173/login
- browser_screenshot label="after-logout"
- Get current URL with browser_evaluate('() => window.location.href')
- Call test_assert: description="After logout stays on /login", condition=True if "login" in URL else False, expected="URL contains /login", actual=the URL you got

### Step 3: Troducer Login
- browser_click selector="text:ENTER"
- browser_fill selector="placeholder:Email" value="tr2@yopmail.com"
- browser_fill selector="placeholder:Password" value="Troducer123!"
- browser_click selector="text:CONTINUE"
- browser_wait_for url_contains="/troducer"
- browser_screenshot label="troducer-page"
- Get current URL with browser_evaluate('() => window.location.href')
- Call test_assert: description="Troducer login redirects to /troducer", condition=True if "/troducer" in URL else False, expected="/troducer in URL", actual=the URL you got

### Step 4: Wrong Password Test
- Call browser_evaluate('() => { sessionStorage.clear(); }')   (logout troducer first)
- browser_navigate to http://localhost:5173/login
- browser_click selector="text:ENTER"
- browser_fill selector="placeholder:Email" value="admin@nihaogroup.com"
- browser_fill selector="placeholder:Password" value="WrongPassword99!"
- browser_click selector="text:CONTINUE"
- Wait a moment with browser_wait_for timeout_ms=3000 (it may timeout, that is OK)
- browser_screenshot label="wrong-password-test"
- Get current URL with browser_evaluate('() => window.location.href')
- Call test_assert: description="Wrong password keeps user on /login", condition=True if "login" in URL else False, expected="stay on /login", actual=the URL you got

### Step 5: DB Role Summary
- shell_run command="docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role;\\"" timeout=30
- Look at the stdout result
- Call test_assert: description="ADMIN role exists in DB", condition=True if "ADMIN" in the stdout else False, expected="ADMIN in output", actual=first 200 chars of stdout
- Call test_assert: description="TRODUCER role exists in DB", condition=True if "TRODUCER" in the stdout else False, expected="TRODUCER in output", actual=first 200 chars of stdout

After completing all 5 steps and their assertions, you are done. Do not do anything extra.
"""
