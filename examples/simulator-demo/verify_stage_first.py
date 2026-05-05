#!/usr/bin/env python3
"""Verify Stage-first governance behaviors across all three scenarios."""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Set

def check_scenario_01(db_path: Path) -> Dict[str, bool]:
    """Verify Scenario 01: Discovery and Stage-first metadata."""
    checks = {}

    if not db_path.exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check 1: skill.read events exist
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE event_type = 'skill.read'")
    read_count = cursor.fetchone()[0]
    checks["skill.read events"] = read_count >= 2  # Read both staged and no-stage skills

    # Check 2: tool.call events with deny for unavailable tool
    cursor.execute("""
        SELECT decision FROM audit_log
        WHERE event_type = 'tool.call' AND decision = 'deny'
    """)
    deny_events = cursor.fetchall()
    checks["unavailable tool denied"] = len(deny_events) > 0

    conn.close()
    return checks

def check_scenario_02(db_path: Path) -> Dict[str, bool]:
    """Verify Scenario 02: Stage transition governance."""
    checks = {}

    if not db_path.exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check 1: stage.transition.allow events
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE event_type = 'stage.transition.allow'")
    allow_count = cursor.fetchone()[0]
    checks["stage.transition.allow events"] = allow_count >= 1

    # Check 2: stage.transition.deny events
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE event_type = 'stage.transition.deny'")
    deny_count = cursor.fetchone()[0]
    checks["stage.transition.deny events"] = deny_count >= 1

    # Check 3: error_bucket in deny events
    cursor.execute("""
        SELECT detail FROM audit_log
        WHERE event_type = 'stage.transition.deny'
    """)
    deny_events = cursor.fetchall()
    has_error_bucket = False
    for (detail,) in deny_events:
        if detail:
            data = json.loads(detail)
            if "error_bucket" in data and data["error_bucket"] == "stage_transition_not_allowed":
                has_error_bucket = True
                break
    checks["error_bucket in deny"] = has_error_bucket

    # Check 4: Legal transition (analysis → execution)
    cursor.execute("""
        SELECT detail FROM audit_log
        WHERE event_type = 'stage.transition.allow'
    """)
    allow_events = cursor.fetchall()
    has_legal_transition = False
    for (detail,) in allow_events:
        if detail:
            data = json.loads(detail)
            if data.get("from_stage") == "analysis" and data.get("to_stage") == "execution":
                has_legal_transition = True
                break
    checks["legal transition (analysis→execution)"] = has_legal_transition

    # Check 5: Illegal transition (execution → analysis)
    has_illegal_transition = False
    for (detail,) in deny_events:
        if detail:
            data = json.loads(detail)
            if data.get("from_stage") == "execution" and data.get("to_stage") == "analysis":
                has_illegal_transition = True
                break
    checks["illegal transition (execution→analysis)"] = has_illegal_transition

    conn.close()
    return checks

def check_scenario_03(db_path: Path) -> Dict[str, bool]:
    """Verify Scenario 03: Terminal stage, persistence, and expiration."""
    checks = {}

    if not db_path.exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check 1: Terminal stage deny (verification → execution)
    cursor.execute("""
        SELECT detail FROM audit_log
        WHERE event_type = 'stage.transition.deny'
    """)
    deny_events = cursor.fetchall()
    has_terminal_deny = False
    for (detail,) in deny_events:
        if detail:
            data = json.loads(detail)
            if data.get("from_stage") == "verification" and data.get("to_stage") == "execution":
                has_terminal_deny = True
                break
    checks["terminal stage blocks transition"] = has_terminal_deny

    # Check 2: Stage state persistence (verify multiple stage transitions occurred)
    # If stage state persists correctly, we should see multiple transitions in order
    cursor.execute("""
        SELECT detail FROM audit_log
        WHERE event_type = 'stage.transition.allow'
        ORDER BY timestamp
    """)
    transitions = cursor.fetchall()
    has_stage_state = False
    if len(transitions) >= 2:
        # Verify we have the expected transition sequence
        first = json.loads(transitions[0][0])
        second = json.loads(transitions[1][0])
        # analysis → execution → verification
        has_stage_state = (
            first.get("from_stage") == "analysis" and
            first.get("to_stage") == "execution" and
            second.get("from_stage") == "execution" and
            second.get("to_stage") == "verification"
        )
    checks["stage state persists"] = has_stage_state

    # Check 3: Expired grant (grant.expire event)
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE event_type = 'grant.expire'")
    expire_count = cursor.fetchone()[0]
    checks["grant.expire event"] = expire_count >= 1

    # Check 4: Tool denied after expiration
    cursor.execute("""
        SELECT decision FROM audit_log
        WHERE event_type = 'tool.call' AND decision = 'deny'
        ORDER BY timestamp DESC
    """)
    deny_tool_events = cursor.fetchall()
    has_post_expire_deny = len(deny_tool_events) >= 2  # At least 2 denies (one after expire, one after disable)
    checks["tool denied after expiration"] = has_post_expire_deny

    # Check 5: disable_skill event
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE event_type = 'skill.disable'")
    disable_count = cursor.fetchone()[0]
    checks["skill.disable event"] = disable_count >= 1

    conn.close()
    return checks

def main():
    scenarios = {
        "Scenario 01 (Discovery)": {
            "db": Path(".scenario-01-data/governance.db"),
            "checker": check_scenario_01,
        },
        "Scenario 02 (Stage Transitions)": {
            "db": Path(".scenario-02-data/governance.db"),
            "checker": check_scenario_02,
        },
        "Scenario 03 (Lifecycle)": {
            "db": Path(".scenario-03-data/governance.db"),
            "checker": check_scenario_03,
        },
    }

    print("=== Stage-first Governance Verification ===\n")

    all_passed = True
    for name, config in scenarios.items():
        print(f"{name}:")
        checks = config["checker"](config["db"])

        if "error" in checks:
            print(f"  ❌ {checks['error']}")
            all_passed = False
            continue

        for check_name, passed in checks.items():
            status = "✓" if passed else "❌"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        print()

    print("=== Summary ===")
    if all_passed:
        print("✅ All Stage-first governance checks passed")
        return 0
    else:
        print("❌ Some checks failed")
        return 1

if __name__ == "__main__":
    exit(main())
