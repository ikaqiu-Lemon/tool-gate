#!/usr/bin/env python3
"""Stage D verification: Check all 7 governance decision events are covered."""

import sqlite3
from pathlib import Path

# Define the 7 governance decision events from ACCEPTANCE_CRITERIA.md
REQUIRED_EVENTS = {
    'skill.read',      # Skill metadata queries
    'skill.enable',    # Skill activation with grant creation
    'skill.disable',   # Skill deactivation with grant revocation
    'grant.expire',    # Automatic grant expiration (TTL-based)
    'grant.revoke',    # Explicit grant revocation
    'tool.call',       # Tool authorization decisions (allow/deny)
    'stage.change',    # Stage transitions that modify allowed_tools
}

def check_scenario(scenario_name: str, db_path: Path) -> set[str]:
    """Return set of event_types found in the scenario's audit_log."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT event_type FROM audit_log")
    events = {row[0] for row in cursor.fetchall()}
    conn.close()
    return events

def main():
    scenarios = {
        'Scenario 01': Path('.scenario-01-data/governance.db'),
        'Scenario 02': Path('.scenario-02-data/governance.db'),
        'Scenario 03': Path('.scenario-03-data/governance.db'),
    }
    
    print("=== Stage D Governance Decision Event Coverage ===\n")
    
    all_events = set()
    for name, db_path in scenarios.items():
        if not db_path.exists():
            print(f"❌ {name}: Database not found at {db_path}")
            continue
        
        events = check_scenario(name, db_path)
        all_events.update(events)
        print(f"{name}:")
        print(f"  Events: {sorted(events)}")
        print()
    
    print("=== Coverage Summary ===")
    print(f"Required events (7): {sorted(REQUIRED_EVENTS)}")
    print(f"Found events: {sorted(all_events)}")
    print()
    
    missing = REQUIRED_EVENTS - all_events
    extra = all_events - REQUIRED_EVENTS
    
    if missing:
        print(f"❌ Missing events: {sorted(missing)}")
    if extra:
        print(f"ℹ️  Extra events (not required): {sorted(extra)}")
    
    if not missing:
        print("✅ All 7 governance decision events covered (100%)")
        return 0
    else:
        print(f"❌ Coverage: {len(all_events & REQUIRED_EVENTS)}/7 ({100 * len(all_events & REQUIRED_EVENTS) // 7}%)")
        return 1

if __name__ == '__main__':
    exit(main())
