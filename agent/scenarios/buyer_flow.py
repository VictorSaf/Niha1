# agent/scenarios/buyer_flow.py
"""Scenario: Verify buyer CEA purchase and swap are visible in dashboard."""

PROMPT = """
Test that the buyer_flow_01 user (role=EUA) can log in and see their portfolio.

## Steps:

### 1. Check DB State
shell_run("docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email, role, is_active FROM users WHERE email='buyer_flow_01@yopmail.com';\\"")
Assert: role = EUA (has completed the full flow)

### 2. Login as buyer_flow_01
Navigate to http://localhost:5173/login, click ENTER
Fill buyer_flow_01@yopmail.com / Buyer2024!
Click CONTINUE
Assert: Redirects to /dashboard

### 3. Verify Dashboard
Take screenshot "buyer-dashboard"
browser_get_text selector: "main"
Assert: EUA Holdings visible (non-zero)
Assert: CEA Cash link is visible in nav

### 4. Verify Order History
Click "Completed" tab in Order History
Assert: At least one BUY CEA order visible
Assert: At least one SWAP order visible
Take screenshot "buyer-order-history"

### 5. Check for Console Errors
browser_get_console_errors()
Assert: No critical JS errors (errors array is empty or contains only warnings)

Report PASS/FAIL.
"""
