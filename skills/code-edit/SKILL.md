---
name: Code Edit
description: "Code editing with staged access: analysis (read-only) then execution (write)."
risk_level: medium
version: "1.0.0"
default_ttl: 3600
allowed_ops:
  - analyze
  - edit
stages:
  - stage_id: analysis
    description: "Read-only analysis phase — understand the code before modifying."
    allowed_tools:
      - Read
      - Glob
      - Grep
  - stage_id: execution
    description: "Write phase — apply changes after analysis."
    allowed_tools:
      - Read
      - Edit
      - Write
---

# Code Edit

Staged code editing workflow — first analyze, then execute.

## Workflow

1. Start in the **analysis** stage to understand the code
2. Use `change_stage("code-edit", "execution")` when ready to edit
3. Apply changes using Edit or Write tools

## Rules

- Always start in analysis stage
- Only move to execution after understanding the impact
- Prefer Edit over Write for modifying existing files
