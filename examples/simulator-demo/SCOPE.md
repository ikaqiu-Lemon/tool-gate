# Simulator Demo Scope

This document maps the three existing examples to simulator demo capabilities, establishing clear boundaries for what the simulator will demonstrate.

## Skill Fixtures

The simulator uses two skill fixtures in `fixtures/skills/` to demonstrate Stage-first governance:

### yuque-doc-edit-staged (Staged Skill)

A three-stage skill demonstrating Stage-first governance:
- **initial_stage**: `analysis`
- **Stages**: `analysis` → `execution` → `verification`
- **Terminal stage**: `verification` has `allowed_next_stages: []`, blocking further transitions
- **Stage-specific tools**: Each stage defines its own `allowed_tools` list
- **Demonstrates**: Stage transition governance, terminal stage behavior, stage-aware tool filtering

### yuque-knowledge-link (No-Stage Skill)

A no-stage skill demonstrating backward compatibility:
- **No stages field**: Uses `allowed_tools` directly at skill level
- **No initial_stage**: Falls back to skill-level tool authorization
- **Demonstrates**: Backward compatibility for skills that don't adopt Stage-first model

## Scenario Coverage

### Scenario 01: Stage-first Discovery and Metadata

**Validates**:
- `list_skills` discovers both staged and no-stage skills
- `read_skill` returns complete stage workflow metadata (initial_stage, stages, allowed_tools, allowed_next_stages)
- No-stage skills show fallback behavior (skill-level allowed_tools)
- Terminal stages identified via `allowed_next_stages: []`
- Unauthorized tools denied with `tool_not_available`

**Uses**: Both skill fixtures (yuque-doc-edit-staged, yuque-knowledge-link)
- Basic discovery flow: list_skills → read_skill → enable_skill
- Whitelist enforcement: allowed tools pass, unauthorized tools denied
- Mixed MCP environment: multiple MCP servers registered, only enabled skill's tools allowed
- refresh_skills for dynamic skill discovery (appendix)

**Maps to Scenario 01 (Discovery)**:
- SessionStart → skill catalog injection
- list_skills (MCP meta-tool)
- read_skill("yuque-knowledge-link") (MCP meta-tool)
- enable_skill("yuque-knowledge-link") → auto-grant (low risk)
- UserPromptSubmit → active_tools recompute
- PreToolUse("yuque_search") → allow (in runtime available tool set)
- PostToolUse("yuque_search") → audit
- PreToolUse("rag_paper_search") → deny (tool_not_available, not in enabled skill)

**Governance behaviors demonstrated**:
- Auto-grant for low-risk skills
- Runtime available tool set enforcement (allow vs. deny)
- Mixed MCP environment (only enabled skill's tools allowed)
- Audit trail: session.start, skill.read, skill.enable, tool.call (allow), tool.call (deny)

---

### Scenario 02: Stage Transition Governance

**Validates**:
- `enable_skill` enters `initial_stage` automatically
- `active_tools` reflects only current stage's `allowed_tools`
- Legal transitions succeed (analysis → execution within `allowed_next_stages`)
- Illegal transitions denied with `stage_transition_not_allowed` (execution → analysis not in `allowed_next_stages`)
- Audit events: `stage.transition.allow`, `stage.transition.deny`
- Stage state persists to SQLite (`current_stage`, `stage_history`, `exited_stages`)

**Uses**: yuque-doc-edit-staged (three-stage workflow)

### Example 03: lifecycle-and-risk → Scenario 03: Lifecycle and Risk

**Example 03 demonstrates**:
- TTL expiration and automatic grant cleanup
- disable_skill with strict revoke → disable audit ordering (D7 invariant)
- High-risk skill with approval_required (enable_skill denied)
- Two-layer defense: approval_required + blocked_tools
- Long-running session state management

**Maps to Scenario 03 (Lifecycle)**:
- SessionStart (with pre-existing grant that has expired)
- UserPromptSubmit → cleanup_expired_grants → grant.expire event
- PreToolUse("yuque_search") → deny (expired skill, tool_not_available)
- enable_skill("yuque-knowledge-link") → re-grant (low risk, auto)
- disable_skill("yuque-doc-edit") → grant.revoke + skill.disable (strict ordering)
### Scenario 03: Lifecycle, Terminal Stages, and Expiration

**Validates**:
- Full stage lifecycle (analysis → execution → verification)
- Terminal stage blocks further transitions (verification has `allowed_next_stages: []`)
- Stage state persistence and restoration from SQLite
- Expired grants (TTL elapsed) do not contribute tools to `active_tools`
- `disable_skill` removes tools from `active_tools`
- Audit events: `stage.transition.allow`, `stage.transition.deny`, `grant.expire`, `skill.disable`

**Uses**: yuque-doc-edit-staged (terminal stage: verification), yuque-knowledge-link (for TTL expiration test)

---

## Common Governance Chain (All Scenarios)

These elements appear in all three scenarios and form the core governance chain:

1. **SessionStart hook**: Initialize state, inject skill catalog into additionalContext
2. **UserPromptSubmit hook**: Cleanup expired grants, recompute active_tools, inject updated context
3. **PreToolUse hook**: Check active_tools, return allow/deny decision
4. **PostToolUse hook**: Write audit event, update last_used_at
5. **MCP meta-tools**: enable_skill, disable_skill, change_stage, list_skills, read_skill, grant_status, run_skill_action, refresh_skills
6. **SQLite shared state**: Grants, skills_loaded, audit_log, session_state
7. **Policy evaluation**: risk_level → auto/reason/approval, require_reason, blocked_tools, max_ttl
8. **Audit trail**: All governance events with timestamps and ordering

---

## Scenario-Specific Capabilities

### Scenario 01 Only
- Discovery of staged and no-stage skills
- Stage-first metadata validation (initial_stage, stages, allowed_tools)
- No-stage skill fallback behavior (skill-level allowed_tools)
- Unauthorized tool rejection (tool_not_available)

### Scenario 02 Only
- Initial stage entry on enable_skill
- Stage transition governance (legal vs illegal transitions)
- Active tools change with current_stage
- Stage state persistence (current_stage, stage_history, exited_stages)

### Scenario 03 Only
- Full stage lifecycle (analysis → execution → verification)
- Terminal stage blocks further transitions
- Expired grants do not contribute tools to active_tools
- disable_skill removes tools from active_tools

---

## What the Simulator Does NOT Do

To prevent scope creep, the simulator explicitly does NOT:

1. **Implement new governance features**: Only demonstrates existing Stage-first capabilities
2. **Replace existing examples**: Legacy examples remain for historical reference
3. **Modify src/ implementation**: Uses existing tg-hook and tg-mcp binaries as-is
4. **Create a testing framework**: This is a demonstration tool, not a test harness
5. **Support arbitrary scenarios**: Only the three scenarios demonstrating Stage-first governance
6. **Mock subprocess communication**: Uses real tg-hook and tg-mcp subprocesses
7. **Clean up expired grants from skills_loaded**: Expired grants are filtered at runtime but remain in persisted state until explicit cleanup

---

## Scope Boundaries

**In Scope**:
- Demonstrate Stage-first governance (stage workflow metadata, transitions, terminal stages)
- Validate subprocess isolation (real tg-hook and tg-mcp processes)
- Verify protocol correctness (hook stdin/stdout, MCP stdio)
- Verify shared state integrity (SQLite WAL coordination)
- Generate complete audit trails (stage.transition.allow/deny, grant.expire, tool.call)
- Support three core scenarios (discovery, transition governance, lifecycle)
- Provide verification mechanisms (audit completeness, state consistency)

**Out of Scope**:
- Core runtime refactoring (src/tool_governance/)
- Legacy example migration or deletion
- Fourth scenario or custom scenario support
- Tool registry, Redis, or workflow engine integration
- Complex human approval workflows
- Runtime unit test refactoring
- Bug fixes in core runtime (unless directly blocking demo acceptance)

**Out of Scope**:
- New governance features or capabilities
- Changes to src/tool_governance/ implementation
- Changes to existing examples (01, 02, 03)
- General-purpose testing framework
- Support for custom scenarios beyond the three core ones
- In-process simulation (must use real subprocesses)

---

## Success Criteria

The simulator successfully demonstrates the governance chain if:

1. ✅ All three scenarios run to completion
2. ✅ All 9 audit event types are produced across scenarios
3. ✅ Subprocess isolation is verified (real tg-hook and tg-mcp processes)
4. ✅ Protocol correctness is verified (JSON-RPC and stdio formats)
5. ✅ Shared state integrity is verified (MCP writes, hooks read via SQLite)
6. ✅ Allow/deny decisions match expectations (runtime available tool set, blocked_tools, require_reason, approval_required)
7. ✅ Session artifacts are generated (events.jsonl, audit_summary.md, metrics.json, state snapshots)
