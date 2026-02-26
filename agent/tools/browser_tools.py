# agent/tools/browser_tools.py
"""
Playwright-based browser tool implementations.
Each function mirrors the tool schema defined in tool_schemas.py.
"""
import base64
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# Module-level state — single browser instance per agent run
_playwright = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_console_errors: list[str] = []
_screenshots: list[dict] = []  # [{label, path, url, timestamp}]
_output_dir: str = "/tmp/niha_agent"


def init_browser(headless: bool = False, output_dir: str = "/tmp/niha_agent") -> None:
    """Start Chromium. headless=False shows the browser window (required for demo)."""
    global _playwright, _browser, _context, _page, _console_errors, _screenshots, _output_dir
    # Reset per-run state so re-init in the same process starts clean
    _console_errors = []
    _screenshots = []
    _output_dir = output_dir
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=headless,
        args=["--auto-open-devtools-for-tabs"]  # Opens DevTools panel automatically
    )
    _context = _browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=output_dir if not headless else None
    )
    _page = _context.new_page()
    # Capture console errors
    _page.on("console", lambda msg: _console_errors.append(
        f"[{msg.type.upper()}] {msg.text}"
    ) if msg.type in ("error", "warning") else None)
    _page.on("pageerror", lambda err: _console_errors.append(f"[PAGE ERROR] {err}"))


def close_browser() -> None:
    global _playwright, _browser, _context, _page
    if _context:
        _context.close()
    if _browser:
        _browser.close()
    if _playwright:
        _playwright.stop()
    # Reset globals so _get_page() raises RuntimeError on next call before init_browser()
    _page = _context = _browser = _playwright = None


def _get_page() -> Page:
    if _page is None:
        raise RuntimeError("Browser not initialized. Call init_browser() first.")
    return _page


def browser_navigate(url: str) -> dict:
    page = _get_page()
    response = page.goto(url, wait_until="networkidle", timeout=15000)
    return {
        "url": page.url,
        "title": page.title(),
        "status": response.status if response else None
    }


def browser_click(selector: str, screenshot_after: bool = True) -> dict:
    page = _get_page()
    try:
        if selector.startswith("text:"):
            page.get_by_text(selector[5:], exact=False).first.click()
        elif selector.startswith("role:"):
            # role:button:Submit
            parts = selector[5:].split(":", 1)
            page.get_by_role(parts[0], name=parts[1] if len(parts) > 1 else "").click()
        else:
            page.locator(selector).first.click()
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception as e:
        return {"error": str(e), "url": page.url}

    result = {"url": page.url, "title": page.title()}
    if screenshot_after:
        ss = _take_screenshot(f"after_click_{selector[:30]}")
        result["screenshot"] = ss
    return result


def browser_fill(selector: str, value: str) -> dict:
    page = _get_page()
    try:
        if selector.startswith("label:"):
            page.get_by_label(selector[6:]).fill(value)
        elif selector.startswith("placeholder:"):
            page.get_by_placeholder(selector[12:]).fill(value)
        else:
            page.locator(selector).fill(value)
    except Exception as e:
        return {"error": str(e)}
    return {"filled": True, "selector": selector, "value": value}


def browser_screenshot(label: str, full_page: bool = False) -> dict:
    return _take_screenshot(label, full_page=full_page)


def _take_screenshot(label: str, full_page: bool = False) -> dict:
    page = _get_page()
    output_dir = Path(_output_dir)
    filename = f"{int(time.time() * 1000)}_{label[:40].replace(' ', '_')}.png"
    path = output_dir / filename
    page.screenshot(path=str(path), full_page=full_page)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    record = {
        "label": label,
        "path": str(path),
        "url": page.url,
        "timestamp": time.time(),
        "base64": b64[:100] + "..."  # truncate for LLM context
    }
    _screenshots.append(record)
    return {k: v for k, v in record.items() if k != "base64"}


def browser_upload_file(path: str, selector: str = "input[type=file]") -> dict:
    """Upload a file using Playwright's set_input_files (works on hidden file inputs)."""
    page = _get_page()
    try:
        page.locator(selector).first.set_input_files(path)
        return {"uploaded": True, "path": path, "selector": selector}
    except Exception as e:
        return {"error": str(e)}


def browser_get_text(selector: str | None = None) -> dict:
    page = _get_page()
    try:
        if selector:
            text = page.locator(selector).first.inner_text(timeout=5000)
        else:
            text = page.inner_text("body")
        return {"text": text[:2000]}  # cap at 2k chars for LLM context
    except Exception as e:
        return {"error": str(e)}


def browser_wait_for(
    selector: str | None = None,
    url_contains: str | None = None,
    timeout_ms: int = 10000
) -> dict:
    page = _get_page()
    try:
        if url_contains:
            page.wait_for_url(f"**{url_contains}**", timeout=timeout_ms)
            return {"url": page.url}
        elif selector:
            page.wait_for_selector(selector, timeout=timeout_ms)
            return {"found": selector, "url": page.url}
    except Exception as e:
        return {"error": str(e), "url": page.url}
    return {"url": page.url}


def browser_get_console_errors() -> dict:
    return {"errors": _console_errors.copy(), "count": len(_console_errors)}


def browser_evaluate(script: str) -> dict:
    page = _get_page()
    try:
        result = page.evaluate(script)
        return {"result": str(result)[:1000]}
    except Exception as e:
        return {"error": str(e)}


def get_all_screenshots() -> list[dict]:
    return _screenshots
