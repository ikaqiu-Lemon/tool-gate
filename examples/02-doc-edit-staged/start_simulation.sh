#!/bin/bash
# start_simulation.sh - Unified entry point for Example 02 simulation

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Example 02: Doc Edit Staged Simulation"
echo "=========================================="
echo ""

# Set up environment variables
export GOVERNANCE_DATA_DIR="$SCRIPT_DIR/.demo-data"
export GOVERNANCE_SKILLS_DIR="$SCRIPT_DIR/skills"
export GOVERNANCE_CONFIG_DIR="$SCRIPT_DIR/config"
export GOVERNANCE_LOG_DIR="$SCRIPT_DIR/logs"

# Ensure log directory exists
mkdir -p "$GOVERNANCE_LOG_DIR"

echo "Environment:"
echo "  DATA_DIR:   $GOVERNANCE_DATA_DIR"
echo "  SKILLS_DIR: $GOVERNANCE_SKILLS_DIR"
echo "  CONFIG_DIR: $GOVERNANCE_CONFIG_DIR"
echo "  LOG_DIR:    $GOVERNANCE_LOG_DIR"
echo ""

# Run the agent
echo "Starting agent..."
echo ""
python3 "$SCRIPT_DIR/scripts/agent_realistic_simulation.py" "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ✅ Simulation completed successfully"
    echo "=========================================="
    echo ""

    # Find the latest session directory
    LATEST_SESSION=$(ls -td "$GOVERNANCE_LOG_DIR"/session_* 2>/dev/null | head -1)

    if [ -n "$LATEST_SESSION" ]; then
        echo "View logs:"
        echo "  cat $LATEST_SESSION/audit_summary.md"
        echo "  cat $LATEST_SESSION/metrics.json"
        echo "  cat $LATEST_SESSION/events.jsonl"
        echo ""

        # Quick validation
        echo "Quick validation:"
        python3 -c "import json; events = [json.loads(line) for line in open('$LATEST_SESSION/events.jsonl')]; print(f'  ✅ JSONL: {len(events)} events')" 2>/dev/null || echo "  ⚠️  Could not validate JSONL"
        python3 -c "import json; m = json.load(open('$LATEST_SESSION/metrics.json')); print(f'  ✅ Metrics: {m[\"total_tool_calls\"]} tool calls, {m[\"denied_tool_calls\"]} denied')" 2>/dev/null || echo "  ⚠️  Could not validate metrics"
        echo ""
    fi
else
    echo ""
    echo "=========================================="
    echo "  ❌ Simulation failed with code $exit_code"
    echo "=========================================="
    echo ""
fi

exit $exit_code
