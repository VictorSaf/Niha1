from fastapi.testclient import TestClient

from app.main import app


def test_run_endpoint_supports_dry_run() -> None:
    client = TestClient(app)
    payload = {
        "project_id": "niha",
        "task_type": "coding",
        "prompt": "Create a helper function.",
        "dry_run": True,
        "requires_tool_calling": False,
        "requires_json": False,
        "sensitivity_level": "internal",
    }

    response = client.post("/v1/agents/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["selected_model"] == "coder-main"
    assert body["provider"] == "ollama"
    assert body["dry_run"] is True


def test_run_endpoint_returns_fallback_when_confidence_is_low() -> None:
    client = TestClient(app)
    payload = {
        "project_id": "niha",
        "task_type": "analysis",
        "prompt": "Summarize this architecture.",
        "dry_run": False,
        "requires_tool_calling": False,
        "requires_json": False,
        "sensitivity_level": "internal",
        "confidence_score": 0.2,
    }

    response = client.post("/v1/agents/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "cloud-fallback"
    assert body["output"] is None
    assert body["reason"] == "low-confidence"


def test_run_endpoint_maps_provider_error_to_503(monkeypatch) -> None:
    client = TestClient(app)

    async def _raise_error(self, model: str, prompt: str) -> str:
        raise RuntimeError("provider-down")

    from app.providers.ollama_client import OllamaClient
    monkeypatch.setattr(OllamaClient, "generate", _raise_error)

    payload = {
        "project_id": "niha",
        "task_type": "coding",
        "prompt": "Write helper",
        "dry_run": False,
    }
    response = client.post("/v1/agents/run", json=payload)
    assert response.status_code == 503
    assert "provider-down" in response.json()["detail"]


def test_run_endpoint_includes_context_in_prompt(monkeypatch) -> None:
    client = TestClient(app)
    captured: dict[str, str] = {}

    async def _capture(self, model: str, prompt: str) -> str:
        captured["prompt"] = prompt
        return "ok"

    from app.providers.ollama_client import OllamaClient
    monkeypatch.setattr(OllamaClient, "generate", _capture)

    payload = {
        "project_id": "niha",
        "task_type": "coding",
        "prompt": "Implement function",
        "context": "Current file is helpers.py",
        "dry_run": False,
    }

    response = client.post("/v1/agents/run", json=payload)
    assert response.status_code == 200
    assert "Current file is helpers.py" in captured["prompt"]
