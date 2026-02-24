# agent/tools/shell_tools.py
"""
Shell/filesystem tools — equivalent to MCP Desktop Commander.
Runs subprocesses, reads/writes files, queries Docker logs.
"""
import subprocess
import json
from pathlib import Path

_test_results: list[dict] = []  # Accumulated test_assert results


def shell_run(command: str, timeout: int = 30) -> dict:
    """Run any shell command. Safe for read-only ops; writable for fixes."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/Users/victorsafta/work/Niha"
        )
        return {
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}


def shell_read_file(path: str) -> dict:
    try:
        content = Path(path).read_text(errors="replace")
        return {"content": content[:5000], "path": path, "size": len(content)}
    except Exception as e:
        return {"error": str(e), "path": path}


def shell_write_file(path: str, content: str) -> dict:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"written": True, "path": path, "size": len(content)}
    except Exception as e:
        return {"error": str(e), "path": path}


def test_assert(
    description: str,
    condition: bool,
    expected: str,
    actual: str
) -> dict:
    """Record a test assertion. Returns result dict."""
    result = {
        "description": description,
        "status": "PASS" if condition else "FAIL",
        "expected": expected,
        "actual": actual
    }
    _test_results.append(result)
    return result


def get_test_results() -> list[dict]:
    return _test_results.copy()


def get_test_summary() -> dict:
    passed = sum(1 for r in _test_results if r["status"] == "PASS")
    failed = sum(1 for r in _test_results if r["status"] == "FAIL")
    return {
        "total": len(_test_results),
        "passed": passed,
        "failed": failed,
        "success": failed == 0
    }


# Pre-built helper commands the agent will call frequently
HELPER_COMMANDS = {
    "backend_logs_recent": "docker compose logs backend --since 2m 2>&1 | tail -50",
    "check_db_user": lambda email: f"docker compose exec db psql -U niha_user -d niha_carbon -c \"SELECT email, role, is_active FROM users WHERE email='{email}';\"",
    "restart_backend": "docker compose restart backend",
}
