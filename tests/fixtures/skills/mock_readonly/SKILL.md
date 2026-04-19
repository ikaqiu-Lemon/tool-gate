---
name: Mock Readonly
description: "Low-risk read-only fixture for happy-path functional tests."
risk_level: low
allowed_tools:
  - mock_read
  - mock_glob
allowed_ops:
  - search
  - read_file
default_ttl: 3600
version: "1.0.0"
---

# Mock Readonly

Fixture skill for the functional test harness. Exercises the happy path:
low-risk auto-grant, stage-less `allowed_tools`, two `allowed_ops`.
