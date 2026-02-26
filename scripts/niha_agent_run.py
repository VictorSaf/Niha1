#!/usr/bin/env python3
"""
Runner: coordonează agentul backend + frontend dintr-un singur terminal.
Comenzi: login [email] [password] | backend get/ask | frontend goto/click/ask | dashboard | exit
Credențiale pentru „login”: NIHA_LOGIN_EMAIL, NIHA_LOGIN_PASSWORD (sau le dai pe linia de comandă).
"""
import os
import sys

# Allow running from repo root or from scripts/
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from niha_agent_backend import BackendAgent
from niha_agent_frontend import FrontendAgent

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


def run_login(backend: BackendAgent, frontend: FrontendAgent, email: str, password: str) -> bool:
    """Login pe backend + pe frontend (browser: /login -> ENTER -> fill -> CONTINUE)."""
    if not backend.login(email, password):
        print("Backend login failed.")
        return False
    print("Backend: OK.")
    if not frontend.goto("/login"):
        print("Frontend: goto /login failed.")
        return True
    if not frontend.click("ENTER"):
        print("Frontend: click ENTER failed (already on form?).")
    frontend.fill("input[type=email]", email)
    frontend.fill("input[type=password]", password)
    if not frontend.click("CONTINUE"):
        frontend.click("Continue")
    print("Frontend: form submitted.")
    return True


def main():
    backend = BackendAgent()
    frontend = FrontendAgent()
    frontend.start()
    print("--- NIHA Agent Runner (backend + frontend) ---")
    print(f"Backend: {BACKEND_URL}  Frontend: {FRONTEND_URL}")
    print("Comenzi: login [email] [password] | backend get <path> | backend ask <...> | frontend goto <path> | frontend click <text> | frontend ask <...> | dashboard | exit")
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

            if cmd in ("exit", "quit"):
                print("Bye.")
                break

            if cmd == "login":
                args = rest.split()
                email = os.environ.get("NIHA_LOGIN_EMAIL") or (args[0] if args else None)
                password = os.environ.get("NIHA_LOGIN_PASSWORD") or (args[1] if len(args) > 1 else None)
                if not email or not password:
                    print("Set NIHA_LOGIN_EMAIL și NIHA_LOGIN_PASSWORD sau: login email parola")
                    continue
                run_login(backend, frontend, email, password)

            elif cmd == "backend":
                sub = rest.split(maxsplit=1)
                sub_cmd = (sub[0] or "").lower()
                sub_rest = (sub[1] or "").strip()
                if sub_cmd == "get":
                    path = sub_rest.split()[0] if sub_rest else ""
                    if path:
                        code, text = backend.get(path)
                        print(code)
                        print(text[:2000])
                    else:
                        print("backend get <path>")
                elif sub_cmd == "ask":
                    if sub_rest:
                        print(backend.ask(sub_rest))
                    else:
                        print("backend ask <întrebare>")
                else:
                    print("backend get <path> | backend ask <...>")

            elif cmd == "frontend":
                sub = rest.split(maxsplit=1)
                sub_cmd = (sub[0] or "").lower()
                sub_rest = (sub[1] or "").strip()
                if sub_cmd == "goto":
                    if sub_rest:
                        frontend.goto(sub_rest.split()[0])
                        print(frontend._page.url if frontend._page else "OK")
                    else:
                        print("frontend goto <path>")
                elif sub_cmd == "click":
                    if sub_rest:
                        ok = frontend.click(sub_rest)
                        print("OK." if ok else "click failed")
                    else:
                        print("frontend click <text>")
                elif sub_cmd == "ask":
                    if sub_rest:
                        print(frontend.ask(sub_rest))
                    else:
                        print("frontend ask <...>")
                else:
                    print("frontend goto <path> | frontend click <text> | frontend ask <...>")

            elif cmd == "dashboard":
                frontend.goto("/dashboard")
                print(frontend._page.url if frontend._page else "OK")

            else:
                print("Comenzi: login | backend get/ask | frontend goto/click/ask | dashboard | exit")
    finally:
        frontend.stop()


if __name__ == "__main__":
    main()
