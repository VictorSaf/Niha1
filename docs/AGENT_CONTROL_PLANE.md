# Agent Control Plane

Standalone local-first service for reusable agent orchestration across projects.

## Location

- Service code: `agent-control-plane/`
- Entrypoint: `agent-control-plane/app/main.py`

## Purpose

- Route agent tasks to local Ollama model profiles
- Expose a stable API contract reusable by other projects
- Provide fallback signaling rules (without forcing cloud execution in this version)

## API Endpoints

### `GET /health`

Returns service status.

Response:

```json
{
  "status": "ok",
  "service": "agent-control-plane"
}
```

### `GET /v1/agents/models`

Lists configured model profiles.

Response (example):

```json
{
  "models": {
    "general": "qwen3-default",
    "coder": "coder-main",
    "coder_fast": "coder-fast",
    "reasoner": "reasoner",
    "tools_strict": "tools-strict",
    "embedder": "mxbai-embed-large"
  }
}
```

### `POST /v1/agents/policies/test`

Validates routing decision for an input task.

Request:

```json
{
  "task_type": "coding",
  "requires_tool_calling": false,
  "requires_json": false,
  "sensitivity_level": "internal"
}
```

Response:

```json
{
  "selected_model": "coder-main",
  "escalate_to_cloud": false,
  "reason": "coding-task"
}
```

### `POST /v1/agents/run`

Runs (or dry-runs) an agent task.

Request:

```json
{
  "project_id": "niha",
  "task_type": "coding",
  "prompt": "Create a helper function for retries.",
  "context": "Current module: app/services/retries.py",
  "requires_tool_calling": false,
  "requires_json": false,
  "sensitivity_level": "internal",
  "timeout_seconds": 12,
  "confidence_score": 0.92,
  "structured_output_valid": true,
  "dry_run": true
}
```

Response (dry-run):

```json
{
  "selected_model": "coder-main",
  "provider": "ollama",
  "dry_run": true,
  "output": null,
  "reason": "coding-task"
}
```

Response (fallback signal example):

```json
{
  "selected_model": "qwen3-default",
  "provider": "cloud-fallback",
  "dry_run": false,
  "output": null,
  "reason": "low-confidence"
}
```

## Environment Variables

- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- `OLLAMA_TIMEOUT_SECONDS` (default `45`)
- `FALLBACK_TIMEOUT_SECONDS` (default `45`)
- `FALLBACK_CONFIDENCE_THRESHOLD` (default `0.7`)

## Run Locally

```bash
cd agent-control-plane
/opt/homebrew/bin/python3.13 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
./.venv/bin/uvicorn app.main:app --reload --port 8010
```

## Tests

```bash
cd agent-control-plane
./.venv/bin/pytest tests -q
```

## Troubleshooting

- `503` from `/v1/agents/run`: verify `OLLAMA_BASE_URL`, model availability (`ollama list`), and Ollama process state.
- Unexpected fallback responses: verify payload values for `confidence_score`, `timeout_seconds`, and `sensitivity_level`.
- Empty output from Ollama: confirm model prompt format and that `/api/chat` returns `message.content`.
