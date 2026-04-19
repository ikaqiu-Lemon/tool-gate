---
name: Mock Stageful
description: "Medium-risk two-stage fixture for change_stage tests."
risk_level: medium
allowed_ops:
  - analyze
  - edit
stages:
  - stage_id: analysis
    description: "Read-only analysis stage."
    allowed_tools:
      - mock_read
      - mock_glob
  - stage_id: execution
    description: "Write stage."
    allowed_tools:
      - mock_edit
      - mock_write
default_ttl: 3600
version: "1.0.0"
---

# Mock Stageful

Fixture skill exercising staged `allowed_tools`. Default stage = analysis
(first listed). `change_stage` → execution swaps in the write tool set.
Medium-risk path requires a `reason` under the default policy.
