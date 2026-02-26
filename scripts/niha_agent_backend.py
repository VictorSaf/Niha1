#!/usr/bin/env python3
"""
Agent care vorbește direct cu backend-ul NIHA (API). Din terminal: login, get/post, ask Ollama.
Usage:
  python scripts/niha_agent_backend.py
  Comenzi: login <email> <parolă> | get <path> | post <path> [body] | ask <întrebare> | exit
Necesită: pip install -r scripts/requirements-agent.txt (requests). Opțional: Ollama pentru ask.

Next step: rulezi acest agent într-un terminal și agentul frontend în altul; poți adăuga un
runner care pornește amândoi și le dă instrucțiuni din același flux (opțional).
"""
import json
import os
import sys

try:
    import requests
except ImportError:
    print("Lipsește requests. Rulează: pip install -r scripts/requirements-agent.txt", file=sys.stderr)
    sys.exit(1)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
API_BASE = f"{BACKEND_URL}/api/v1"


class BackendAgent:
    """API callable: login(), get(path), post(path, body), ask(question)."""

    def __init__(
        self,
        backend_url: str | None = None,
        ollama_host: str | None = None,
        ollama_model: str | None = None,
    ):
        self.backend_url = backend_url or BACKEND_URL
        self.api_base = f"{self.backend_url}/api/v1"
        self.ollama_host = ollama_host or OLLAMA_HOST
        self.ollama_model = ollama_model or OLLAMA_MODEL
        self.token: str | None = None
        self.last_response_text: str = ""

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

    def login(self, email: str, password: str) -> bool:
        try:
            r = requests.post(
                f"{self.api_base}/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            self.token = data.get("access_token")
            self.last_response_text = r.text
            return True
        except requests.exceptions.RequestException:
            return False

    def get(self, path: str) -> tuple[int, str]:
        path = path.lstrip("/")
        url = f"{self.api_base}/{path}" if not path.startswith("api/") else f"{self.backend_url}/{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            self.last_response_text = r.text
            return r.status_code, r.text
        except requests.exceptions.RequestException as e:
            return 0, str(e)

    def post(self, path: str, body: dict) -> tuple[int, str]:
        path = path.lstrip("/")
        url = f"{self.api_base}/{path}" if not path.startswith("api/") else f"{self.backend_url}/{path}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = requests.post(url, json=body, headers=headers, timeout=15)
            self.last_response_text = r.text
            return r.status_code, r.text
        except requests.exceptions.RequestException as e:
            return 0, str(e)

    def ask(self, question: str) -> str:
        system = (
            f"You are a backend agent for NIHA. API base: {self.api_base}. "
            "Answer briefly; suggest API paths if relevant. Reply in the same language as the user."
        )
        context = f"Last API response (if any): {self.last_response_text[:1500]}" if self.last_response_text else "No previous response."
        return self._ollama(system, f"[Context: {context}]\nUser: {question}")


def _cmd_login(agent: BackendAgent, args: list[str]) -> bool:
    if len(args) < 2:
        print("Usage: login <email> <parolă>")
        return False
    ok = agent.login(args[0], args[1])
    if ok:
        print("OK. Logat.")
    else:
        print("Login failed.")
    return ok


def _cmd_get(agent: BackendAgent, args: list[str]) -> bool:
    if not args:
        print("Usage: get <path>")
        return False
    code, text = agent.get(args[0])
    print(code)
    try:
        print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
    except Exception:
        print(text[:2000])
    return True


def _cmd_post(agent: BackendAgent, args: list[str]) -> bool:
    if not args:
        print("Usage: post <path> [json body]")
        return False
    body = args[1] if len(args) > 1 else "{}"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("Body must be valid JSON")
        return False
    code, text = agent.post(args[0], data)
    print(code)
    try:
        print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
    except Exception:
        print(text[:2000])
    return True


def _cmd_ask(agent: BackendAgent, args: list[str]) -> bool:
    if not args:
        print("Usage: ask <întrebare>")
        return False
    print(agent.ask(" ".join(args)))
    return True


def main():
    agent = BackendAgent()
    print("--- NIHA Backend Agent ---")
    print(f"Backend: {BACKEND_URL}  |  Comenzi: login, get, post, ask, exit")
    print()
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        rest = (parts[1] or "").strip()
        args = rest.split() if rest else []
        if cmd == "exit" or cmd == "quit":
            print("Bye.")
            break
        if cmd == "login":
            _cmd_login(agent, args)
        elif cmd == "get":
            _cmd_get(agent, args)
        elif cmd == "post":
            if rest:
                idx = rest.find("{")
                if idx >= 0:
                    args = [rest[:idx].strip().strip("/")] + [rest[idx:]]
            _cmd_post(agent, args)
        elif cmd == "ask":
            _cmd_ask(agent, [rest] if rest else [])
        else:
            print("Comenzi: login, get, post, ask, exit")


if __name__ == "__main__":
    main()
