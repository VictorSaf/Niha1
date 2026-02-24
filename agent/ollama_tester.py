#!/usr/bin/env python3
# agent/ollama_tester.py
"""
NIHA Platform E2E Test Agent
Powered by qwen3:8b via Ollama + Playwright + subprocess (Desktop Commander)

Usage:
    python3 ollama_tester.py --scenario troducer_flow
    python3 ollama_tester.py --scenario login_flow
    python3 ollama_tester.py --scenario buyer_flow
    python3 ollama_tester.py --prompt "Test that admin can approve an NDA in backoffice"
"""
import json
import time
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import ollama

from tools.tool_schemas import ALL_TOOLS
from tools.browser_tools import (
    init_browser, close_browser, get_all_screenshots,
    browser_navigate, browser_click, browser_fill,
    browser_screenshot, browser_get_text, browser_wait_for,
    browser_get_console_errors, browser_evaluate
)
from tools.shell_tools import (
    shell_run, shell_read_file, shell_write_file,
    test_assert, get_test_results, get_test_summary
)

console = Console()

MODEL = "qwen3:8b"
PLATFORM_URL = "http://localhost:5173"
API_URL = "http://localhost:8000"
MAX_ITERATIONS = 40  # Safety limit

SYSTEM_PROMPT = """You are an expert QA engineer testing the NIHA Carbon Trading Platform.

## Platform Info
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000 (FastAPI, NOT Django — there is no manage.py)
- Health check: curl http://localhost:8000/health → {"status":"healthy"}
- Admin login: admin@nihaogroup.com / Admin123!
- Troducer login: tr2@yopmail.com / Troducer123!

## Tech Stack (IMPORTANT)
- Backend: FastAPI + PostgreSQL (Docker). Debug with: docker compose logs backend --since 2m
- Frontend: React 18 + Zustand state management
- Auth storage: Zustand uses SESSIONSTORAGE (not localStorage!) key "auth-storage"
- To check if logged in: browser_evaluate('() => { const s = sessionStorage.getItem("auth-storage"); return s ? "TOKEN_FOUND" : "NO_TOKEN"; }')
- To logout properly: browser_evaluate('() => { sessionStorage.clear(); }') then browser_navigate to http://localhost:5173/login
  After sessionStorage.clear() + navigate, React reloads fresh → stays on /login (no redirect)
- NEVER use localStorage.clear() for logout — auth is in sessionStorage, not localStorage
- NEVER use manage.py — this is FastAPI, not Django

## Your Testing Approach
1. PLAN: Think through all steps before executing
2. EXECUTE: Use browser tools to navigate and interact
3. ASSERT: After each major action, take a screenshot and call test_assert
4. SKIP & CONTINUE: If a step fails TWICE in a row, call test_assert with condition=False and move to the NEXT step
5. DEBUG: If something fails, use shell_run to check docker compose logs backend --since 1m 2>&1 | tail -30

## Tool Usage Rules
- Always call browser_screenshot with a descriptive label after important actions
- After login, call browser_wait_for(url_contains="/dashboard") or url_contains="/troducer"
- Use test_assert for EVERY verification
- If the same command fails 2+ times: give up on that step, assert FAIL, continue to next step
- Use browser_get_console_errors() after each page load to catch JS errors

## Selectors Guide (NIHA platform)
- Login ENTER button: "text:ENTER"
- Email input: "placeholder:Email"
- Password input: "placeholder:Password"
- CONTINUE button: "text:CONTINUE"
- NDA button on login: "text:NDA"
- Backoffice nav: "text:Onboarding"
- Approve NDA button: "text:Approve NDA"

## Important: Assert Everything, Skip Stuck Steps
Every test step must end with test_assert. If stuck on a step:
- Call test_assert with condition=False to record the failure
- Move on to the next step in the scenario
- Do NOT retry the same failing command more than 2 times

When you are done testing, summarize all results and call test_assert for an overall PASS/FAIL.
"""


def dispatch_tool(name: str, args: dict) -> str:
    """Route tool calls to implementations. Returns JSON string result."""
    tool_map = {
        "browser_navigate": browser_navigate,
        "browser_click": browser_click,
        "browser_fill": browser_fill,
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
    fn = tool_map.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**args)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})


def run_agent(scenario_prompt: str, headless: bool = False) -> dict:
    """Main agent loop. Returns final test summary."""
    console.print(Panel(
        f"[bold cyan]NIHA E2E Test Agent[/bold cyan]\n"
        f"Model: [green]{MODEL}[/green] | "
        f"Scenario: [yellow]{scenario_prompt[:80]}[/yellow]",
        border_style="cyan"
    ))

    # Init browser (headless=False shows the browser window)
    console.print("[dim]Starting browser...[/dim]")
    init_browser(headless=headless, output_dir="/tmp/niha_agent")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Test scenario:\n\n{scenario_prompt}\n\nBegin testing now. Take screenshots at each step."}
    ]

    iteration = 0
    start_time = time.time()
    recent_calls: list[str] = []  # Last N tool signatures for loop detection

    try:
        while iteration < MAX_ITERATIONS:
            iteration += 1
            console.print(f"\n[dim]-- Iteration {iteration}/{MAX_ITERATIONS} --[/dim]")

            # Call Ollama — disable thinking for tool-calling steps (faster)
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=ALL_TOOLS,
                options={"temperature": 0.1},
                think=False  # Disable thinking mode for speed during tool execution
            )

            msg = response.message
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls or []})

            # If the model produced text (status update or final answer)
            if msg.content:
                console.print(Panel(msg.content, title="[bold]Agent[/bold]", border_style="blue"))

            # If no tool calls → agent is done
            if not msg.tool_calls:
                console.print("[green bold]Agent finished -- no more tool calls[/green bold]")
                break

            # Execute each tool call
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments or {}

                console.print(f"  [cyan]-> {tool_name}[/cyan] {json.dumps(tool_args)[:120]}")

                result_str = dispatch_tool(tool_name, tool_args)
                result_obj = json.loads(result_str)

                # Show result summary
                if "error" in result_obj:
                    console.print(f"    [red]ERROR: {result_obj['error']}[/red]")
                elif tool_name == "test_assert":
                    status = result_obj.get("status", "?")
                    color = "green" if status == "PASS" else "red"
                    console.print(f"    [{color}]{status}: {result_obj['description']}[/{color}]")
                elif tool_name == "browser_screenshot":
                    console.print(f"    [dim]Screenshot: {result_obj.get('path', '?')}[/dim]")
                else:
                    preview = result_str[:150].replace('\n', ' ')
                    console.print(f"    [dim]{preview}[/dim]")

                messages.append({
                    "role": "tool",
                    "content": result_str
                })

                # Loop detection: if same tool called 3 times in a row, inject guidance
                call_sig = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)[:60]}"
                recent_calls.append(call_sig)
                recent_calls = recent_calls[-6:]  # Keep last 6
                if len(recent_calls) >= 3 and len(set(recent_calls[-3:])) == 1:
                    console.print("[yellow]Loop detected — injecting guidance message[/yellow]")
                    messages.append({
                        "role": "user",
                        "content": "STOP: You have called the same tool with the same arguments 3 times in a row. This approach is not working. Record a FAIL assertion for the current step using test_assert, then move on to the NEXT step in the scenario. Do not retry this command again."
                    })
                    recent_calls.clear()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    finally:
        close_browser()

    elapsed = time.time() - start_time
    summary = get_test_summary()
    screenshots = get_all_screenshots()

    # Print final table
    table = Table(title="Test Results", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="bold", width=6)
    table.add_column("Description", min_width=40)
    table.add_column("Expected", style="dim")
    table.add_column("Actual", style="dim")

    for r in get_test_results():
        color = "green" if r["status"] == "PASS" else "red"
        table.add_row(
            f"[{color}]{r['status']}[/{color}]",
            r["description"],
            r.get("expected", "")[:40],
            r.get("actual", "")[:40]
        )
    console.print(table)

    overall_color = "green" if summary["success"] else "red"
    console.print(Panel(
        f"[{overall_color}]{'PASSED' if summary['success'] else 'FAILED'}[/{overall_color}] "
        f"-- {summary['passed']}/{summary['total']} assertions passed "
        f"-- {elapsed:.1f}s -- {iteration} iterations -- {len(screenshots)} screenshots",
        border_style=overall_color
    ))

    try:
        from reporter.dashboard import generate_report
        report_path = generate_report(
            scenario=scenario_prompt[:50],
            model=MODEL,
            results=get_test_results(),
            screenshots=get_all_screenshots(),
            elapsed=elapsed,
            iteration_count=iteration,
        )
        console.print(f"\n[green]Report saved:[/green] file://{report_path}")
        import subprocess
        subprocess.Popen(["open", report_path])  # Auto-open in browser on macOS
    except Exception as e:
        console.print(f"[yellow]Report generation failed (results still collected): {e}[/yellow]")

    return {**summary, "screenshots": screenshots, "elapsed": elapsed, "iterations": iteration}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NIHA E2E Test Agent (Ollama)")
    parser.add_argument("--scenario", choices=["troducer_flow", "login_flow", "buyer_flow"], help="Built-in scenario")
    parser.add_argument("--prompt", type=str, help="Custom test prompt")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (default: visible)")
    parser.add_argument("--model", default=MODEL, help=f"Ollama model to use (default: {MODEL})")
    args = parser.parse_args()

    if args.model:
        MODEL = args.model

    if args.scenario:
        from scenarios import troducer_flow, login_flow, buyer_flow
        scenarios = {
            "troducer_flow": troducer_flow.PROMPT,
            "login_flow": login_flow.PROMPT,
            "buyer_flow": buyer_flow.PROMPT,
        }
        prompt = scenarios[args.scenario]
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        exit(1)

    result = run_agent(prompt, headless=args.headless)
    exit(0 if result["success"] else 1)
