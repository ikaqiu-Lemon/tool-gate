---
name: Mock Refreshable
description: "Low-risk fixture dropped in mid-test to validate refresh_skills."
risk_level: low
allowed_tools:
  - mock_noop
allowed_ops:
  - noop
default_ttl: 3600
version: "1.0.0"
---

# Mock Refreshable

Fixture skill used by the `refresh_skills` functional test. Pattern:
initial tree excludes this skill; test copies this SKILL.md into the
tmp-dir skills root, calls `refresh_skills()`, and asserts the new skill
becomes visible via `list_skills()` with exactly one `build_index` call.
