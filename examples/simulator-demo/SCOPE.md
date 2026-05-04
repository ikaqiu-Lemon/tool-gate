# Simulator Demo Scope

This document maps the three existing examples to simulator demo capabilities, establishing clear boundaries for what the simulator will demonstrate.

## Example-to-Scenario Mapping

### Example 01: knowledge-link → Scenario 01: Discovery

**Example 01 demonstrates**:
- Low-risk skill with auto-grant (no reason required)
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

### Example 02: doc-edit-staged → Scenario 02: Staged Workflow

**Example 02 demonstrates**:
- Medium-risk skill with require_reason enforcement
- Two-stage workflow: analysis (read-only) → execution (write)
- Stage-aware tool filtering: different tools per stage
- change_stage mechanics and audit trail
- blocked_tools global red line (run_command always denied)

**Maps to Scenario 02 (Staged)**:
- enable_skill("yuque-doc-edit") without reason → deny (reason_missing)
- enable_skill("yuque-doc-edit", reason="...") → grant with stage=analysis
- UserPromptSubmit → active_tools = analysis stage tools
- PreToolUse("yuque_get_doc") → allow (in analysis stage)
- PreToolUse("yuque_update_doc") → deny (not in analysis stage)
- change_stage("yuque-doc-edit", "execution") (MCP meta-tool)
- UserPromptSubmit → active_tools = execution stage tools
- PreToolUse("yuque_update_doc") → allow (in execution stage)
- PreToolUse("run_command") → deny (blocked_tools, global red line)

**Governance behaviors demonstrated**:
- require_reason enforcement (deny without reason, grant with reason)
- Stage transitions via change_stage
- Stage-aware tool filtering
- blocked_tools global red line (overrides any skill authorization)
- Audit trail: skill.enable (denied), skill.enable (granted), stage.change, tool.call (deny/allow)

---

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
- enable_skill("yuque-bulk-delete") → deny (approval_required, high risk)

**Governance behaviors demonstrated**:
- TTL expiration and automatic cleanup
- Grant revocation with strict audit ordering (revoke before disable)
- High-risk skill denial (approval_required)
- Re-authorization after expiration
- Audit trail: grant.expire, skill.enable (granted), grant.revoke, skill.disable, skill.enable (denied)

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
- Auto-grant for low-risk skills
- Mixed MCP environment demonstration
- Basic tool_not_available (unauthorized tool from different MCP)

### Scenario 02 Only
- require_reason enforcement
- Stage transitions (analysis → execution)
- Stage-aware tool filtering
- blocked_tools global red line

### Scenario 03 Only
- TTL expiration and cleanup
- Grant revocation with strict ordering
- High-risk skill denial (approval_required)
- Re-authorization after expiration

---

## What the Simulator Does NOT Do

To prevent scope creep, the simulator explicitly does NOT:

1. **Implement new governance features**: Only demonstrates existing capabilities from examples
2. **Replace existing examples**: Examples 01, 02, 03 remain the canonical end-to-end demos
3. **Modify src/ implementation**: Uses existing tg-hook and tg-mcp binaries as-is
4. **Create a testing framework**: This is a demonstration tool, not a test harness
5. **Support arbitrary scenarios**: Only the three scenarios derived from examples
6. **Mock subprocess communication**: Uses real tg-hook and tg-mcp subprocesses
7. **Invent new skills or policies**: Reuses skills and policies from examples

---

## Scope Boundaries

**In Scope**:
- Demonstrate subprocess isolation (real tg-hook and tg-mcp processes)
- Validate protocol correctness (JSON-RPC for hooks, stdio for MCP)
- Verify shared state integrity (SQLite WAL coordination)
- Generate complete audit trails (all 9 event types)
- Support three core scenarios (discovery, staged, lifecycle)
- Provide verification mechanisms (audit completeness, state consistency)

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
