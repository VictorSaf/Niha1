# agent/scenarios/login_flow.py
"""Scenario: Login flow for all roles."""

PROMPT = """
Test the login flow for multiple user roles on the NIHA platform.

## IMPORTANT AUTH FACTS
- Auth is in SESSIONSTORAGE key 'auth-storage' (NOT localStorage)
- Logout: browser_evaluate('() => { sessionStorage.clear(); }') then navigate to http://localhost:5173/login
- Check token: browser_evaluate('() => { const s = sessionStorage.getItem("auth-storage"); return s ? "TOKEN_FOUND" : "NO_TOKEN"; }')
- WebSocket warnings in console are NORMAL — ignore them completely

## Steps (follow EXACTLY in order, do not add extra steps):

### Step 1: Admin Login
1. browser_navigate("http://localhost:5173/login")
2. browser_click("text:ENTER")
3. browser_fill("placeholder:Email", "admin@nihaogroup.com")
4. browser_fill("placeholder:Password", "Admin123!")
5. browser_click("text:CONTINUE")
6. browser_wait_for(url_contains="/dashboard")
7. browser_screenshot("admin-dashboard")
8. test_assert("Admin login redirects to /dashboard", True if "/dashboard" in url else False, "/dashboard", current_url)
9. browser_evaluate to check TOKEN_FOUND
10. test_assert("Token in sessionStorage", True if result=="TOKEN_FOUND" else False, "TOKEN_FOUND", result)

### Step 2: Logout Admin
1. browser_evaluate('() => { sessionStorage.clear(); }')
2. browser_navigate("http://localhost:5173/login")
3. browser_screenshot("after-logout-login-page")
4. test_assert("After logout URL is /login", True if url=="/login" or url contains "login", "/login", current_url)

### Step 3: Troducer Login
1. browser_click("text:ENTER")
2. browser_fill("placeholder:Email", "tr2@yopmail.com")
3. browser_fill("placeholder:Password", "Troducer123!")
4. browser_click("text:CONTINUE")
5. browser_wait_for(url_contains="/troducer")
6. browser_screenshot("troducer-page")
7. test_assert("Troducer login redirects to /troducer", True if "/troducer" in url, "/troducer", current_url)

### Step 4: Wrong Password Test
1. browser_evaluate('() => { sessionStorage.clear(); }')   ← MUST DO THIS FIRST to logout troducer
2. browser_navigate("http://localhost:5173/login")
3. browser_click("text:ENTER")
4. browser_fill("placeholder:Email", "admin@nihaogroup.com")
5. browser_fill("placeholder:Password", "WrongPassword99!")
6. browser_click("text:CONTINUE")
7. Wait 2s: browser_wait_for(selector=".text-red-400", timeout_ms=5000) — may fail, that's OK
8. browser_screenshot("login-error-wrong-password")
9. Get page text: browser_get_text()
10. test_assert("Wrong password shows error or stays on /login", True if "/login" in url or "Invalid" in text or "incorrect" in text, "error or /login", f"url={url}")

### Step 5: DB Role Check
1. shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY role;\\"")
2. test_assert("Admin users exist in DB", True if "ADMIN" in stdout, "ADMIN role present", stdout[:100])
3. test_assert("Troducer users exist in DB", True if "TRODUCER" in stdout, "TRODUCER role present", stdout[:100])

After all 5 steps, report overall PASS/FAIL.
"""
