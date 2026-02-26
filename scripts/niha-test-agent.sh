#!/usr/bin/env bash
# NIHA test agent: one-shot or interactive. Ollama answers questions about the running platform.
# Usage:
#   ./scripts/niha-test-agent.sh                    → interactive (ask questions in a loop)
#   ./scripts/niha-test-agent.sh "Întrebare"        → one-shot
# Needs: Ollama (ollama serve, ollama pull llama3.2). Optional: OLLAMA_HOST, OLLAMA_MODEL

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

SYSTEM="You are a tester and guide for the NIHA Carbon Platform. Frontend: $FRONTEND_URL, Backend API: $BACKEND_URL. The user runs the app and asks you questions about what they see, what to do next, or what happened. Reply briefly and in the same language as the user. If context about backend/frontend status is provided, use it."

# Fetch live context (backend health, frontend status) for interactive use
get_live_context() {
  local ctx=""
  if curl -sf --max-time 2 "${BACKEND_URL}/health" >/dev/null 2>&1; then
    ctx="Backend ${BACKEND_URL}: reachable (health OK). "
  else
    ctx="Backend ${BACKEND_URL}: not reachable. "
  fi
  local code
  code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 2 "${FRONTEND_URL}/" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    ctx="${ctx}Frontend ${FRONTEND_URL}: HTTP $code."
  else
    ctx="${ctx}Frontend ${FRONTEND_URL}: HTTP $code or not reachable."
  fi
  echo "$ctx"
}

call_ollama() {
  local prompt="$1"
  local payload
  payload=$(jq -n \
    --arg model "$OLLAMA_MODEL" \
    --arg system "$SYSTEM" \
    --arg prompt "$prompt" \
    '{ model: $model, system: $system, prompt: $prompt, stream: false }')
  local response
  response=$(curl -sf -X POST "${OLLAMA_HOST}/api/generate" \
    -H "Content-Type: application/json" \
    -d "$payload") || { echo "Error: Ollama at $OLLAMA_HOST?"; return 1; }
  if command -v jq >/dev/null 2>&1; then
    echo "$response" | jq -r '.response // .error // .'
  else
    echo "$response"
  fi
}

# Interactive mode: loop until user types exit/quit
run_interactive() {
  echo "--- NIHA test session (interactive) ---"
  echo "Frontend: $FRONTEND_URL  |  Backend: $BACKEND_URL"
  echo "Type your question or instruction, then Enter. Type exit or quit to end."
  echo ""
  while true; do
    echo -n "> "
    read -r line
    [ -z "$line" ] && continue
    case "$line" in
      exit|quit) echo "Bye."; exit 0 ;;
    esac
    CONTEXT=$(get_live_context)
    PROMPT="[Current state: $CONTEXT] User: $line"
    echo ""
    call_ollama "$PROMPT" || true
    echo ""
  done
}

# One-shot: first argument is the instruction
if [ $# -eq 0 ]; then
  run_interactive
else
  INSTRUCTION="$*"
  CONTEXT=$(get_live_context)
  PROMPT="[Current state: $CONTEXT] User: $INSTRUCTION"
  call_ollama "$PROMPT"
fi
