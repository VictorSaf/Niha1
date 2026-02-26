#!/usr/bin/env python3
"""
Agent care interacționează direct cu frontend-ul NIHA (browser). Din terminal: goto, click, fill, snapshot, ask Ollama.
Usage:
  python scripts/niha_agent_frontend.py
  Comenzi: goto <path> | click <text> | fill <selector> <valoare> | snapshot | ask <întrebare> | exit
Necesită: pip install -r scripts/requirements-agent.txt  și  playwright install chromium

Next step: rulezi backend agent într-un terminal, frontend agent în altul; următorul pas logic
e un runner care coordonează amândoi (același flux de comenzi → ambele interfețe) sau
scenarii tip „login pe frontend + verificare date pe backend”.
"""
import os
import sys

try:
    import requests
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print("Lipsește un pachet. Rulează: pip install -r scripts/requirements-agent.txt && playwright install chromium", file=sys.stderr)
    sys.exit(1)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


class FrontendAgent:
    """API callable: start(), goto(path), click(text), fill(selector, value), snapshot(), ask(question), stop()."""

    def __init__(
        self,
        frontend_url: str | None = None,
        ollama_host: str | None = None,
        ollama_model: str | None = None,
        headless: bool = False,
    ):
        self.frontend_url = (frontend_url or FRONTEND_URL).rstrip("/")
        self.ollama_host = ollama_host or OLLAMA_HOST
        self.ollama_model = ollama_model or OLLAMA_MODEL
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None
        self._last_snapshot_path: str = ""

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        ctx = self._browser.new_context(viewport={"width": 1280, "height": 720})
        self._page = ctx.new_page()
        self._page.goto(self.frontend_url, wait_until="domcontentloaded", timeout=15000)

    def stop(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    def _ollama(self, system: str, prompt: str) -> str:
        try:
            r = requests.post(
                f"{self.ollama_host}/api/generate",
                json={"model": self.ollama_model, "system": system, "prompt": prompt, "stream": False},
                timeout=60,
            )
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as e:
            return f"[Ollama error: {e}]"

    def _page_context(self) -> str:
        if not self._page:
            return "Browser not on a page."
        try:
            url = self._page.url
            title = self._page.title()
            buttons = self._page.locator("button, [role='button'], a[href]").all_inner_texts()
            buttons = [t.strip()[:80] for t in buttons if t.strip()][:25]
            return f"URL: {url}\nTitle: {title}\nButtons/links (sample): {buttons}"
        except Exception as e:
            return f"URL: {self._page.url}\nError: {e}"

    def goto(self, path: str) -> bool:
        url = path if path.startswith("http") else f"{self.frontend_url}/{path.lstrip('/')}"
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            return True
        except Exception:
            return False

    def click(self, text: str) -> bool:
        try:
            loc = self._page.get_by_role("button", name=text).or_(self._page.get_by_text(text, exact=False))
            loc.first.click(timeout=5000)
            return True
        except Exception:
            return False

    def fill(self, selector: str, value: str) -> bool:
        try:
            self._page.fill(selector, value, timeout=5000)
            return True
        except Exception:
            return False

    def snapshot(self) -> str:
        out = os.path.join(os.path.dirname(__file__), "..", "agent_snapshot.png")
        self._page.screenshot(path=out)
        self._last_snapshot_path = out
        return out

    def ask(self, question: str) -> str:
        context = self._page_context()
        system = (
            f"You are a frontend tester for NIHA at {self.frontend_url}. "
            "Reply briefly, in the same language as the user."
        )
        return self._ollama(system, f"[Current page]\n{context}\n\nUser: {question}")


def main():
    agent = FrontendAgent(headless=os.environ.get("HEADLESS", "0") == "1")
    print("--- NIHA Frontend Agent ---")
    print(f"Frontend: {FRONTEND_URL}  |  Comenzi: goto, click, fill, snapshot, ask, exit")
    print()
    agent.start()
    print(f"Browser opened at {agent._page.url}")
    print()
    try:
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            rest = (parts[1] or "").strip()
            args = rest.split() if rest else []
            if cmd in ("exit", "quit"):
                print("Bye.")
                break
            if cmd == "goto":
                if args:
                    agent.goto(args[0])
                    print(agent._page.url if agent._page else "OK")
                else:
                    print("Usage: goto <path>")
            elif cmd == "click":
                if args:
                    ok = agent.click(" ".join(args))
                    print("OK." if ok else "click failed")
                else:
                    print("Usage: click <text>")
            elif cmd == "fill":
                if len(args) >= 2:
                    ok = agent.fill(args[0], " ".join(args[1:]))
                    print("OK." if ok else "fill failed")
                else:
                    print("Usage: fill <selector> <valoare>")
            elif cmd == "snapshot":
                p = agent.snapshot()
                print(f"OK. Saved: {p}")
            elif cmd == "ask":
                if args or rest:
                    print(agent.ask(" ".join(args) if args else rest))
                else:
                    print("Usage: ask <întrebare>")
            else:
                print("Comenzi: goto, click, fill, snapshot, ask, exit")
    finally:
        agent.stop()


if __name__ == "__main__":
    main()
