#!/usr/bin/env bash
# Run all three simulator scenarios and generate summary report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Tool-Gate Simulator Demo"
echo "=========================================="
echo ""

# Run Scenario 01
echo "[1/3] Running Scenario 01: Discovery and Auto-Grant..."
python scenarios/scenario_01_discovery.py
echo "✓ Scenario 01 complete"
echo ""

# Run Scenario 02
echo "[2/3] Running Scenario 02: Staged Workflow..."
python scenarios/scenario_02_staged.py
echo "✓ Scenario 02 complete"
echo ""

# Run Scenario 03
echo "[3/3] Running Scenario 03: Grant Lifecycle..."
python scenarios/scenario_03_lifecycle.py
echo "✓ Scenario 03 complete"
echo ""

echo "=========================================="
echo "Running Stage-first Governance Verification"
echo "=========================================="
python3 verify_stage_first.py
VERIFY_EXIT=$?

echo ""
echo "=========================================="
echo "Summary Report"
echo "=========================================="
echo ""
if [ $VERIFY_EXIT -eq 0 ]; then
    echo "✅ All three scenarios completed successfully."
    echo "✅ All Stage-first governance checks passed."
else
    echo "❌ Verification FAILED - see errors above"
    exit 1
fi
echo ""
echo "Generated artifacts:"
echo "  - .scenario-01-data/ (Discovery)"
echo "  - .scenario-02-data/ (Staged)"
echo "  - .scenario-03-data/ (Lifecycle)"
echo ""
echo "Each directory contains:"
echo "  - governance.db (SQLite audit log)"
echo "  - events.jsonl (Complete event trace)"
echo "  - audit_summary.md (Human-readable summary)"
echo "  - metrics.json (Event statistics)"
echo ""
echo "To re-run verification only:"
echo "  python3 verify_stage_first.py"
echo ""
