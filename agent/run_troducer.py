#!/usr/bin/env python3
# [STALE: 2026-04-03] Runner pentru TRODUCER (rol eliminat în feature 0072). Înlocuitor: agent/run_introducer.py (de creat). Vezi docs/STALE_CONTENT.md.
# agent/run_troducer.py
"""
Orchestrated Troducer E2E flow.

Python controls sequencing. Each TC is a short focused mini-agent.
The model can't skip ahead because it only sees one TC at a time.
Python handles DB state extraction between phases.

Usage:
    cd agent && source .venv/bin/activate
    python3 run_troducer.py [--headless] [--model qwen3:14b]
"""
import json
import subprocess
import sys
import time
import argparse
from pathlib import Path

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))

from tools.tool_schemas import ALL_TOOLS
from tools.browser_tools import (
    init_browser, close_browser, get_all_screenshots,
    browser_navigate, browser_click, browser_fill, browser_upload_file,
    browser_screenshot, browser_get_text, browser_wait_for,
    browser_get_console_errors, browser_evaluate,
)
from tools.shell_tools import (
    shell_run, shell_read_file, shell_write_file,
    test_assert, get_test_results, get_test_summary,
)

console = Console()
MODEL = "qwen3:14b"
OUTPUT_DIR = "/tmp/niha_agent"
NIHA_DIR = "/Users/victorsafta/work/Niha"

SYSTEM_PROMPT = """You are a QA engineer testing the NIHA Carbon Trading Platform.
- Frontend: http://localhost:5173
- Auth: sessionStorage key 'auth-storage' (NOT localStorage)
- Logout: browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
- Login sequence: navigate /login → click text:ENTER (reveals fields) → fill Email → fill Password → click text:CONTINUE → wait for redirect
- WebSocket warnings are NORMAL — do NOT debug them, do NOT check docker logs for them
- Execute EXACTLY what is asked. Nothing more.
- Take a screenshot after each action.
- Call test_assert for every verification.
- If a step fails twice, call test_assert with condition=False and stop."""

TOOL_MAP = {
    "browser_navigate": browser_navigate,
    "browser_click": browser_click,
    "browser_fill": browser_fill,
    "browser_upload_file": browser_upload_file,
    "browser_screenshot": browser_screenshot,
    "browser_get_text": browser_get_text,
    "browser_wait_for": browser_wait_for,
    "browser_get_console_errors": browser_get_console_errors,
    "browser_evaluate": browser_evaluate,
    "shell_run": shell_run,
    "shell_read_file": shell_read_file,
    "shell_write_file": shell_write_file,
    "test_assert": test_assert,
}


def db(sql: str) -> str:
    """Run a DB query directly from Python (no agent needed)."""
    r = subprocess.run(
        ["docker", "compose", "exec", "db", "psql", "-U", "niha_user", "-d", "niha_carbon", "-t", "-c", sql],
        capture_output=True, text=True, cwd=NIHA_DIR,
    )
    return r.stdout.strip()


def url_encode(code: str) -> str:
    """URL-encode a referral code for use in query string."""
    return code.replace("$", "%24").replace("!", "%21").replace("#", "%23").replace("@", "%40")


def run_phase(label: str, prompt: str, max_iter: int = 12) -> bool:
    """Run a focused single-TC agent. Returns True if any assertion passed."""
    console.print(Panel(f"[bold cyan]{label}[/bold cyan]", border_style="cyan"))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    recent: list[str] = []

    for i in range(max_iter):
        console.print(f"  [dim]iter {i+1}/{max_iter}[/dim]")
        # Retry up to 3 times on connection errors (model may be loading)
        for attempt in range(3):
            try:
                response = ollama.chat(
                    model=MODEL, messages=messages, tools=ALL_TOOLS,
                    options={"temperature": 0.1}, think=False,
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise
                console.print(f"  [yellow]Ollama error (attempt {attempt+1}): {e} — retrying in 10s[/yellow]")
                time.sleep(10)
        msg = response.message
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls or []})

        if msg.content:
            console.print(f"  [blue]{msg.content[:300]}[/blue]")

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments or {}
            console.print(f"  [cyan]→ {name}[/cyan] {json.dumps(args)[:120]}")

            fn = TOOL_MAP.get(name)
            if not fn:
                result = {"error": f"Unknown tool: {name}"}
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = {"error": str(e)}

            result_str = json.dumps(result, default=str)

            if "error" in result:
                console.print(f"    [red]ERR: {result['error']}[/red]")
            elif name == "test_assert":
                color = "green" if result.get("status") == "PASS" else "red"
                console.print(f"    [{color}]{result.get('status')}: {result.get('description')}[/{color}]")

            messages.append({"role": "tool", "content": result_str})

            # Loop detection
            sig = f"{name}:{json.dumps(args, sort_keys=True)[:50]}"
            recent.append(sig)
            recent = recent[-4:]
            if len(recent) >= 3 and len(set(recent[-3:])) == 1:
                console.print("[yellow]Loop detected — stopping phase[/yellow]")
                messages.append({
                    "role": "user",
                    "content": "STOP looping. Record a FAIL assertion with test_assert, then stop — do not call any more tools.",
                })
                recent.clear()

    return True


def run():
    global MODEL
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    if args.model:
        MODEL = args.model

    start = time.time()
    init_browser(headless=args.headless, output_dir=OUTPUT_DIR)

    try:
        # ── CLEANUP ──────────────────────────────────────────────────────────
        console.print("[dim]Cleanup: removing leftover test data...[/dim]")
        db("DELETE FROM users WHERE email='e2e-auto@yopmail.com';")
        db("DELETE FROM contact_requests WHERE contact_email='e2e-auto@yopmail.com';")

        # ── TC-01: Troducer login + referral code ────────────────────────────
        run_phase("TC-01: Troducer Login + Referral Code", """
Login as troducer and verify the referral code.

1. browser_navigate url="http://localhost:5173/login"
2. browser_click selector="text:ENTER"
3. browser_fill selector="placeholder:Email" value="tr2@yopmail.com"
4. browser_fill selector="placeholder:Password" value="Troducer123!"
5. browser_click selector="text:CONTINUE"
6. browser_wait_for url_contains="/troducer"
7. browser_screenshot label="TC01-troducer-dashboard"
8. browser_get_text() — read text, find the referral code on screen (short code like "Riw9MKF!")
9. shell_run command="docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT referral_code FROM users WHERE email='tr2@yopmail.com';\\""
10. test_assert: description="TC-01: Referral code on screen matches DB", condition=True if they match
""")

        # Python extracts state — no agent needed
        referral_code_raw = db("SELECT referral_code FROM users WHERE email='tr2@yopmail.com';").strip().split("\n")[-1].strip()
        referral_code_url = url_encode(referral_code_raw)
        console.print(f"  [green]Referral code from DB: {referral_code_raw} → URL: {referral_code_url}[/green]")

        # ── TC-02: Submit introducer form ────────────────────────────────────
        run_phase("TC-02: Submit Introducer Form", f"""
Submit the introducer request form. The page has ENTER and NDA buttons — click NDA to open the form.

1. browser_evaluate script="() => {{ sessionStorage.clear(); }}"
2. browser_navigate url="http://localhost:5173/introducer?ref={referral_code_url}"
3. browser_screenshot label="TC02-introducer-landing"
4. browser_click selector="text:NDA"
5. browser_screenshot label="TC02-nda-form-open"
6. browser_fill selector="placeholder:Entity Name (optional)" value="E2E Auto Corp"
7. browser_fill selector="placeholder:Corporate Email" value="e2e-auto@yopmail.com"
8. browser_fill selector="placeholder:First Name" value="Auto"
9. browser_fill selector="placeholder:Last Name" value="Test"
10. browser_fill selector="placeholder:Position in Entity" value="QA"
11. browser_click selector="text:SUBMIT"
12. browser_screenshot label="TC02-submitted"
13. browser_get_text()
14. test_assert: description="TC-02: Form submitted — Request Submitted visible", condition=True if "Request Submitted" in page text
""")

        # ── TC-03: DB verification — PREINTRODUCER ───────────────────────────
        run_phase("TC-03: DB Verification — PREINTRODUCER", """
Verify DB state after form submission.

1. shell_run command="docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email, role, is_active, invitation_token IS NOT NULL as has_token FROM users WHERE email='e2e-auto@yopmail.com';\\""
2. Read the output
3. test_assert: description="TC-03a: role is PREINTRODUCER", condition=True if "PREINTRODUCER" in stdout
4. test_assert: description="TC-03b: is_active is false", condition=True if "| f" or "f " in stdout (the is_active column value)
5. test_assert: description="TC-03c: invitation_token exists", condition=True if "| t" or "t " in stdout (the has_token column value)
""")

        # Wait for DB write to complete (email sending is async after the API returns)
        time.sleep(4)

        # Python extracts invitation token
        token_raw = db("SELECT invitation_token FROM users WHERE email='e2e-auto@yopmail.com';").strip().split("\n")[-1].strip()
        if not token_raw or len(token_raw) < 10:
            console.print(f"  [red]No invitation token found — TC-02 likely failed. Skipping TC-04/05.[/red]")
            test_assert("TC-03-guard: PREINTRODUCER user created", False, "invitation_token in DB", f"got: '{token_raw}'")
            token_raw = "INVALID_TOKEN"
        else:
            console.print(f"  [green]Invitation token from DB: {token_raw[:20]}...[/green]")

        # ── TC-04: Setup password ────────────────────────────────────────────
        run_phase("TC-04: Setup Password via Invitation Link", f"""
Set a password for the new PREINTRODUCER user.

1. browser_navigate url="http://localhost:5173/setup-password?token={token_raw}"
2. browser_screenshot label="TC04-setup-password-page"
3. browser_fill selector="placeholder:Create a strong password" value="AutoTest123!"
4. browser_fill selector="placeholder:Confirm your password" value="AutoTest123!"
5. browser_click selector="text:Set Password & Continue"
6. browser_wait_for timeout_ms=8000
7. browser_screenshot label="TC04-after-submit"
8. browser_get_text()
9. test_assert: description="TC-04: Password set — NDA upload step visible", condition=True if "Upload" in page text or "NDA" in page text or no error visible
""")

        # ── TC-05: NDA Upload ────────────────────────────────────────────────
        run_phase("TC-05: NDA Upload", """
Upload the signed NDA PDF. The page should show "Upload Signed NDA" after the password step.
Use browser_upload_file — do NOT use browser_fill for file uploads.

1. browser_screenshot label="TC05-nda-upload-page"
2. browser_get_text()
3. browser_upload_file path="/Users/victorsafta/work/Niha/backend/uploads/nda/NDA-Niha-signed.pdf" selector="input[type=file]"
4. browser_screenshot label="TC05-file-selected"
5. browser_click selector="text:Upload NDA & Complete Setup"
6. browser_wait_for timeout_ms=8000
7. browser_screenshot label="TC05-after-upload"
8. browser_get_text()
9. test_assert: description="TC-05: NDA uploaded — success message visible", condition=True if "NDA Uploaded" in page text or "submitted for review" in page text
""")

        # ── TC-06: Admin approves NDA ────────────────────────────────────────
        run_phase("TC-06: Admin Approves NDA in Backoffice", """
Login as admin and approve the NDA. The button text is "Approve NDA".

1. browser_evaluate script="() => { sessionStorage.clear(); }"
2. browser_navigate url="http://localhost:5173/login"
3. browser_click selector="text:ENTER"
4. browser_fill selector="placeholder:Email" value="admin@nihaogroup.com"
5. browser_fill selector="placeholder:Password" value="Admin123!"
6. browser_click selector="text:CONTINUE"
7. browser_wait_for url_contains="/dashboard"
8. browser_screenshot label="TC06-admin-dashboard"
9. browser_navigate url="http://localhost:5173/backoffice/onboarding/requests"
10. browser_screenshot label="TC06-onboarding-requests"
11. browser_get_text()
12. browser_click selector="aria-label:Approve NDA for E2E Auto Corp"
13. browser_wait_for timeout_ms=5000
14. browser_screenshot label="TC06-after-approval"
15. browser_get_text()
16. test_assert: description="TC-06: NDA approved — entry gone or status changed", condition=True if "E2E Auto Corp" not in page text or "Approve NDA" not in page text
""")

        # ── TC-07: Final DB verification ─────────────────────────────────────
        run_phase("TC-07: Final DB Verification", """
Verify DB shows INTRODUCER role, active, nda_signed after admin approval.

1. shell_run command="docker compose exec db psql -U niha_user -d niha_carbon -c \\"SELECT email, role, is_active, nda_signed FROM users WHERE email='e2e-auto@yopmail.com';\\""
2. Read the output carefully
3. test_assert: description="TC-07a: role is INTRODUCER", condition=True if "INTRODUCER" in stdout and "PREINTRODUCER" not in stdout
4. test_assert: description="TC-07b: is_active is true", condition=True if "| t" in stdout (is_active column)
5. test_assert: description="TC-07c: nda_signed is true", condition=True if "| t" in stdout (nda_signed column)
""")

    finally:
        close_browser()

    # ── Cleanup ──────────────────────────────────────────────────────────────
    console.print("[dim]Final cleanup...[/dim]")
    db("DELETE FROM users WHERE email='e2e-auto@yopmail.com';")
    db("DELETE FROM contact_requests WHERE contact_email='e2e-auto@yopmail.com';")

    elapsed = time.time() - start
    results = get_test_results()
    summary = get_test_summary()
    screenshots = get_all_screenshots()

    # Print results table
    table = Table(title="Troducer E2E Results", show_header=True, header_style="bold magenta")
    table.add_column("Status", width=6)
    table.add_column("Description", min_width=45)
    table.add_column("Expected", style="dim")
    table.add_column("Actual", style="dim")
    for r in results:
        color = "green" if r["status"] == "PASS" else "red"
        table.add_row(
            f"[{color}]{r['status']}[/{color}]",
            r["description"],
            r.get("expected", "")[:35],
            r.get("actual", "")[:35],
        )
    console.print(table)

    color = "green" if summary["success"] else "red"
    console.print(Panel(
        f"[{color}]{'PASSED' if summary['success'] else 'FAILED'}[/{color}] "
        f"— {summary['passed']}/{summary['total']} assertions — "
        f"{elapsed:.0f}s — {len(screenshots)} screenshots",
        border_style=color,
    ))

    # Generate HTML report
    try:
        from reporter.dashboard import generate_report
        report_path = generate_report(
            scenario="Troducer E2E Flow",
            model=MODEL,
            results=results,
            screenshots=screenshots,
            elapsed=elapsed,
            iteration_count=0,
        )
        console.print(f"[green]Report:[/green] file://{report_path}")
        import subprocess as _sp
        _sp.Popen(["open", report_path])
    except Exception as e:
        console.print(f"[yellow]Report failed: {e}[/yellow]")

    return summary["success"]


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
