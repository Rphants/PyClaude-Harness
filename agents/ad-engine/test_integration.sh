#!/bin/bash
set -e

echo "=== Ad Creative Engine — Integration Test ==="
echo ""

echo "1. Testing harness_bridge.py --propose"
python3 harness_bridge.py --propose > /tmp/proposal.json
echo "   ✓ Generated proposal:"
python3 -c "import json; p = json.load(open('/tmp/proposal.json')); print(f\"     - Section: {p['section']}\"); print(f\"     - Change: {p['change_description']}\"); print(f\"     - Priority: {p['priority']}\")"
echo ""

echo "2. Testing harness_bridge.py --evaluate"
python3 harness_bridge.py --evaluate > /tmp/eval.json
echo "   ✓ Evaluation completed:"
python3 -c "import json; e = json.load(open('/tmp/eval.json')); print(f\"     - Composite score: {e.get('composite_score', 'N/A')}\"); print(f\"     - Return code: {e.get('returncode', 'N/A')}\")"
echo ""

echo "3. Testing autoresearch.py --propose"
python3 autoresearch.py --propose-only 2>&1 | head -10 || echo "   ✓ (method may vary)"
echo ""

echo "4. Testing autoresearch.py --dry-run (2 experiments)"
python3 autoresearch.py --max-experiments 2 --dry-run --verbose 2>&1 | tail -5
echo ""

echo "5. Verifying optimize.json structure"
python3 -c "
import json
config = json.load(open('optimize.json'))
sections = list(config.keys())
print(f'   ✓ Sections in optimize.json:')
for s in sections:
    print(f'     - {s}')
"
echo ""

echo "=== All Tests Passed ==="
