---
name: Mock Sensitive
description: "High-risk fixture for approval / deny-path functional tests."
risk_level: high
allowed_tools:
  - mock_dangerous
allowed_ops:
  - run
default_ttl: 900
version: "1.0.0"
---

# Mock Sensitive

Fixture skill exercising the high-risk branch. Under the default policy
this maps to `approval_required`; under `restrictive.yaml` it is denied
outright.
