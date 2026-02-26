# Review: NIHA test agent script (0060)

## Summary

Single bash script `scripts/niha-test-agent.sh`: one-shot (instruction as arg) or **interactive** (no args → loop: user types questions, script adds live context (backend/frontend reachability) and sends to Ollama, prints response). Docs: CLAUDE.md, README.md. No plan; review on code quality only.

## Implementation quality

- **Scope**: Minimal, single responsibility, no extra deps (curl + jq optional).
- **Ports**: Correct (5173 frontend, 8000 API) in system prompt.
- **Errors**: curl failure exits 1 with message; missing jq falls back to raw JSON.

## Issues

### Major

- None.

### Minor

1. **scripts/niha-test-agent.sh**: Default model `llama3.2` may not be installed; user might see Ollama error. Acceptable for a dev script; already documented in CLAUDE (OLLAMA_MODEL).

2. **scripts/niha-test-agent.sh**: No check that Ollama is reachable before building payload. Low impact; curl will fail with a clear message.

### Critical

- None.

## Recommendations

- Optional: at start of script, `curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null || { echo "Ollama not reachable at $OLLAMA_HOST"; exit 1; }`. Not required for MVP.

## Plan / docs

No plan. CLAUDE.md updated with one command line. No app_truth or design system impact.

## Verdict

Implementation is correct and minimal. No Critical or Major issues to fix. Pipeline can proceed to write_docs.
