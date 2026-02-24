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
- Backend API: http://localhost:8000 (health returns {"status":"healthy"})
- Admin login: admin@nihaogroup.com / Admin123!
- Troducer login: tr2@yopmail.com / Troducer123!

## Your Testing Approach
1. PLAN: Think through all steps before executing
2. EXECUTE: Use browser tools to navigate and interact
3. ASSERT: After each major action, take a screenshot and call test_assert
4. DEBUG: If something fails, use shell_run to check backend logs
5. FIX: If you find a bug in the code, use shell_write_file to fix it, then shell_run to restart

## Tool Usage Rules
- Always call browser_screenshot with a descriptive label after important actions
- After login, call browser_wait_for to confirm redirect happened
- Use test_assert for EVERY verification (don't just observe — assert)
- When a test fails, call shell_run("docker compose logs backend --since 1m 2>&1 | tail -30") to get logs
- Use browser_get_console_errors() to check for JS errors after each page load

## Selectors Guide (NIHA platform)
- Login ENTER button: "text:ENTER"
- Email input: "placeholder:Email"
- Password input: "placeholder:Password"
- CONTINUE button: "text:CONTINUE"
- NDA button on login: "text:NDA"
- Backoffice nav: "text:Onboarding"
- Approve NDA button: CSS ".bg-emerald" or "text:Approve NDA"

## Important: Assert Everything
Every test step must end with test_assert. Example:
- After login → assert URL contains /dashboard or /troducer
- After form submit → assert success message appears
- After approval → assert item disappears from list

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
