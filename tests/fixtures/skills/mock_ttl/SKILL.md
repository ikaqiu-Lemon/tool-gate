---
name: Mock TTL
description: "Low-risk fixture for TTL-expiry reclamation tests."
risk_level: low
allowed_tools:
  - mock_ping
allowed_ops:
  - ping
default_ttl: 60
version: "1.0.0"
---

# Mock TTL

Fixture skill for TTL-expiry tests. Intended usage: create a grant with
`ttl=0`, sleep briefly, then trigger `UserPromptSubmit` to observe the
cleanup sweep emit `grant.expire` and drop the skill from `skills_loaded`.
