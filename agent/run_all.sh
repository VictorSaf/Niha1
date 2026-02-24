#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

echo "=== NIHA E2E Test Suite ==="
echo ""

python3 ollama_tester.py --scenario login_flow --headless --model qwen3:14b && echo "login_flow: PASS" || echo "login_flow: FAIL"
python3 ollama_tester.py --scenario troducer_flow --headless --model qwen3:14b && echo "troducer_flow: PASS" || echo "troducer_flow: FAIL"
python3 ollama_tester.py --scenario buyer_flow --headless --model qwen3:14b && echo "buyer_flow: PASS" || echo "buyer_flow: FAIL"

echo ""
echo "=== Done. Reports in /tmp/niha_agent/ ==="
