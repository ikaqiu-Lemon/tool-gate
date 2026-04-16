---
name: Tool Governance
description: "Manage tool governance: discover, read, and enable skills to control the tool surface."
risk_level: low
version: "1.0.0"
allowed_tools:
  - mcp__tool-governance__list_skills
  - mcp__tool-governance__read_skill
  - mcp__tool-governance__enable_skill
  - mcp__tool-governance__disable_skill
  - mcp__tool-governance__grant_status
  - mcp__tool-governance__run_skill_action
  - mcp__tool-governance__change_stage
  - mcp__tool-governance__refresh_skills
---

# Tool Governance

This skill manages progressive disclosure and authorization of capabilities.

## Workflow

1. Use `list_skills` to discover available skills and their risk levels
2. Use `read_skill(skill_id)` to understand a skill's SOP, boundaries, and allowed tools
3. Use `enable_skill(skill_id)` to explicitly authorize a skill for the current session
4. Use `run_skill_action(skill_id, op, args)` to execute operations within an enabled skill
5. Use `grant_status` to check current authorizations
6. Use `disable_skill(skill_id)` to revoke authorization when no longer needed

## Rules

- Never attempt to use tools outside of enabled skills
- Always read a skill before enabling it
- Prefer the narrowest scope and shortest TTL that satisfies the task
- If a tool call is denied, follow the authorization flow instead of retrying
