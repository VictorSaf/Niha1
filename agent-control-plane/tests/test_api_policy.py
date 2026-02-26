from fastapi.testclient import TestClient

from app.main import app


def test_policy_test_endpoint_returns_selected_model() -> None:
    client = TestClient(app)
    payload = {
        "task_type": "coding",
        "requires_tool_calling": False,
        "requires_json": False,
        "sensitivity_level": "internal",
    }

    response = client.post("/v1/agents/policies/test", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["selected_model"] == "coder-main"
    assert body["escalate_to_cloud"] is False
