from fastapi.testclient import TestClient

from app.main import app


def test_models_endpoint_exposes_default_profiles() -> None:
    client = TestClient(app)

    response = client.get("/v1/agents/models")

    assert response.status_code == 200
    payload = response.json()
    assert "general" in payload["models"]
    assert payload["models"]["general"] == "qwen3-default"
    assert "coder" in payload["models"]
