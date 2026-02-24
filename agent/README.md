# NIHA E2E Test Agent

Ollama-powered browser testing agent for the NIHA Carbon Trading Platform.

## Quick Start

```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium

# Run a scenario
python3 ollama_tester.py --scenario login_flow
python3 ollama_tester.py --scenario troducer_flow
python3 ollama_tester.py --scenario buyer_flow

# Custom prompt
python3 ollama_tester.py --prompt "Test that admin login redirects to /dashboard"

# Headless (no browser window)
python3 ollama_tester.py --scenario login_flow --headless
```

## Requirements
- Ollama running locally with qwen3:8b installed
- NIHA platform running (docker compose up -d)
- Python 3.11+

## Model
Uses `qwen3:8b` by default. Swap with `--model qwen3:14b` for better accuracy at cost of speed.
