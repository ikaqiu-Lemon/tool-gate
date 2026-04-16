---
name: Repo Read
description: "Read-only code exploration: search files, read contents, find patterns."
risk_level: low
version: "1.0.0"
default_ttl: 7200
allowed_tools:
  - Read
  - Glob
  - Grep
allowed_ops:
  - search
  - read_file
---

# Repo Read

Read-only exploration of the repository.

## Workflow

1. Use `Glob` to find files matching a pattern
2. Use `Grep` to search for content within files
3. Use `Read` to view file contents

## Rules

- This skill only provides read access — no modifications allowed
- Prefer Grep for content search, Glob for file discovery
