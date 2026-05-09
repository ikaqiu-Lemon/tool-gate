# Changelog

All notable changes to Stagewise-Tool-Gate are recorded in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-05

**Stage-first Skill Governance** — Major architectural release establishing Skills as business workflows with stage-based tool exposure, not tool groupings. This release formalizes the governance model where Skills represent standard operating procedures (SOPs), Stages represent workflow phases within a Skill, and Tools are external capabilities exposed at each stage. Tool exposure now follows workflow progression, preventing premature access to high-risk operations.

This release completes a three-phase refactor:
1. **formalize-stage-workflow-metadata** — Established stage workflow metadata schema
2. **enforce-stage-transition-governance** — Implemented runtime enforcement of stage transitions
3. **migrate-demos-to-stage-first-governance** — Migrated demonstration layer to Stage-first patterns

### Added

**Stage Workflow Metadata:**
- `initial_stage` field in `SkillMetadata` — Declares entry point stage for staged workflows. When omitted, first stage becomes default entry point.
- `allowed_next_stages` field in `StageDefinition` — Declares valid successor stages from current stage, enabling explicit workflow transition graphs.
- Terminal stage representation — `allowed_next_stages: []` (empty list) marks a stage as terminal, blocking all further transitions.
- Stage-level `allowed_tools` — Defines tool exposure boundary for each stage in staged Skills.
- No-stage Skill support — Skills without stage definitions continue using skill-level `allowed_tools` fallback (fully supported, non-deprecated format).

**Stage Runtime State:**
- `current_stage` tracking — Identifies active stage within enabled staged Skills.
- `stage_entered_at` timestamp — Records when current stage was entered.
- `stage_history` — List of `StageTransitionRecord` entries recording successful transitions (from_stage, to_stage, transitioned_at). Denied transitions are recorded in audit only, not in stage_history.
- `exited_stages` — List of stage IDs that were exited during the session (factual record of stages left, not business-level completion status).

**Stage-Specific Error Taxonomy:**
- `invalid_initial_stage` — `enable_skill` called with non-existent initial_stage reference.
- `stage_not_found` — `change_stage` called with non-existent target stage.
- `stage_not_initialized` — `change_stage` called when current_stage is None (skill not properly initialized).
- `stage_transition_not_allowed` — `change_stage` called with target stage not in current stage's allowed_next_stages.
- `skill_has_no_stages` — `change_stage` called on a no-stage Skill (which uses skill-level allowed_tools fallback).

**Stage Transition Audit Events:**
- `stage.transition.allow` — Successful stage transition with skill_id, from_stage, to_stage, timestamp.
- `stage.transition.deny` — Blocked stage transition with skill_id, from_stage, to_stage, error_bucket, timestamp.
- Note: `stage.change` from earlier demo/spec wording is superseded by `stage.transition.allow` and `stage.transition.deny` in 1.0.0.

**Skill Authoring Documentation:**
- `docs/skill_stage_authoring.md` — Comprehensive authoring standard defining when to decompose Skills into Stages, how to design stage workflows, and anti-patterns to avoid (e.g., splitting by tool type rather than workflow phase).
- Skill/Stage/Tool semantic definitions — Skill = business capability/SOP, Stage = workflow phase, Tool = external capability.
- Design guidance for `initial_stage` selection (safest entry point, typically read-only).
- Design guidance for `allowed_next_stages` (explicit transition graphs, circular/backward transitions allowed for retry patterns).
- Terminal stage expression (`allowed_next_stages: []`).
- Anti-patterns documented — Avoid mechanical splitting by tool type; prefer splitting by workflow phase.

**Canonical Stage-first Demo:**
- `examples/simulator-demo` established as canonical Stage-first governance demonstration.
- Skill fixtures: `yuque-doc-edit-staged` (3-stage workflow: analysis → execution → verification) and `yuque-knowledge-link` (no-stage skill demonstrating fallback behavior).
- Scenario 01: Stage-first discovery — Verifies `read_skill` returns stage metadata (initial_stage, stages, allowed_next_stages), no-stage fallback behavior, and unauthorized tool denial.
- Scenario 02: Stage transition governance — Verifies `enable_skill` enters initial_stage, `active_tools` follows current_stage, legal transitions succeed, illegal transitions denied, and stage.transition.allow/deny audit events.
- Scenario 03: Lifecycle and terminal stages — Verifies terminal stage blocking, stage state persistence (current_stage, stage_history, exited_stages), expired grant via TTL=2s natural expiration, and disable/revoke removes tools.
- `run_simulator.sh` — One-command execution of all three scenarios through real `tg-hook` and `tg-mcp` subprocess boundaries.
- `verify_stage_first.py` — 11 automated Stage-first governance checks validating audit events, transition enforcement, and terminal stage behavior.
- Generated artifacts excluded from version control (`.scenario-*-data/` in `.gitignore`).

### Changed

**`enable_skill` Semantics:**
- Strengthened from "enable tool access" to "authorize and start a business workflow/SOP."
- For staged Skills: Enters `initial_stage` (if configured) or first stage, initializing `current_stage`, `stage_entered_at`, `stage_history`, and `exited_stages`.
- For no-stage Skills: Sets `current_stage=None`, continues using skill-level `allowed_tools` fallback.
- Invalid `initial_stage` fails safely — Returns `invalid_initial_stage` error without creating grant, without adding to skills_loaded, without exposing tools.

**`change_stage` Semantics:**
- Now enforces `allowed_next_stages` validation before allowing transitions.
- Legal transitions: Updates `current_stage`, `stage_entered_at`, appends to `stage_history`, updates `exited_stages`, changes `active_tools` to reflect new stage.
- Illegal transitions: Denies with no state modification, no stage_history entry, records audit event with error_bucket.
- Terminal stages (`allowed_next_stages: []`): Block all further transitions.
- No-stage Skills: Returns `skill_has_no_stages` error, does not affect skill-level allowed_tools fallback.

**`active_tools` Behavior:**
- For staged Skills: Derived from `current_stage.allowed_tools` (stage-level tool exposure).
- For no-stage Skills: Derived from `skill.allowed_tools` (skill-level fallback).
- Expired grants do not contribute tools to `active_tools`.
- `blocked_tools` filtering still applies after stage-based tool selection.
- PreToolUse hook continues checking requested tool against current `active_tools`.

**`read_skill` / `SkillContent` Exposure:**
- `SkillContent.metadata` now includes `initial_stage` field.
- `SkillContent.metadata.stages` now includes `allowed_next_stages` per stage.
- Terminal stages correctly expose `allowed_next_stages: []`.
- No-stage Skills omit `stages` in SKILL.md and may serialize as `stages: []`; runtime treats both as no-stage Skills and uses skill-level `allowed_tools`.
- Does NOT expose runtime state (`current_stage`, `stage_history`, `exited_stages`, `stage_entered_at` remain internal).

**Legacy Examples Deprecated:**
- `examples/01-knowledge-link`, `examples/02-doc-edit-staged`, `examples/03-lifecycle-and-risk` marked as DEPRECATED/Legacy with prominent notices.
- Preserved for historical reference, not deleted.
- Not migrated to Stage-first format.
- Documentation (`examples/README.md`, root `README.md`) updated to direct users to `simulator-demo` for Stage-first patterns.

### Compatibility

**Backward Compatibility Preserved:**
- No-stage Skills remain fully supported (not deprecated) — Skills without stage definitions continue using skill-level `allowed_tools` fallback.
- Existing no-stage Skills continue working unchanged.
- Existing staged Skills without `initial_stage` enter the first stage automatically.
- Existing staged Skills without `allowed_next_stages` still load, but their stages default to terminal behavior (`allowed_next_stages: []`); authors must add `allowed_next_stages` where transitions are expected.
- No SQLite schema migration required — New stage state fields serialize within existing JSON columns.
- No MCP protocol changes — `enable_skill` and `change_stage` return shapes unchanged.

**No Breaking Changes:**
- Existing hook/MCP entrypoint contracts remain compatible. Runtime behavior is extended for Stage-first governance, but no SQLite schema migration or MCP protocol shape change is required.
- Session state with missing new fields deserializes correctly (fields default to None/empty).
- Old audit analysis tools can ignore new event types (`stage.transition.allow`, `stage.transition.deny`).

### Tests and Verification

**Test Coverage:**
- Added broad stage-governance test coverage across model serialization, stage initialization, transition validation, persistence integration, and simulator acceptance.
- Full test suite: 290 tests passing (baseline: 104 at end of Phase 3).
- Simulator acceptance: 3/3 scenarios pass, 11/11 Stage-first governance checks pass.
- All scenarios verified through real `tg-hook` and `tg-mcp` subprocess boundaries (not static mocks).

### Migration Notes

**For Skill Authors:**
- New staged Skills should declare `initial_stage` (safest entry point, typically read-only stage) and `allowed_next_stages` per stage.
- Terminal stages use `allowed_next_stages: []` to block further transitions.
- Simple Skills without workflow phases can continue using skill-level `allowed_tools` (no stages required).
- Invalid `initial_stage` references will cause `enable_skill` to fail — verify stage names match metadata.

**For System Integrators:**
- `LoadedSkillInfo` now includes optional `stage_entered_at`, `stage_history`, `exited_stages` fields.
- Existing session state deserializes correctly (new fields default to None/empty).
- New audit event types: `stage.transition.allow` (successful transitions) and `stage.transition.deny` (blocked transitions with error_bucket).
- Generated demo artifacts (`.scenario-*-data/`) are no longer tracked in version control — run scenarios to regenerate.

**For Users:**
- Legacy examples (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`) are deprecated — use `examples/simulator-demo` for Stage-first patterns.
- Run `examples/simulator-demo/run_simulator.sh` to see Stage-first governance in action.

### Fixed

**Simulator Demo Layer Fixes:**

These fixes affect only the simulator-demo acceptance harness, not core runtime behavior:

1. **`mcp_subprocess.py` list_skills bug** — Fixed MCP wrapper only returning first content block, causing `list_skills` to return incomplete results. Now collects and parses all content blocks correctly.

2. **`core.py` get_state_snapshot bug** — Fixed helper only reading `grants` table, unable to access stage state. Now parses `sessions.state_json.skills_loaded` to extract complete stage state (current_stage, stage_history, exited_stages).

3. **`core.py` enable_skill TTL support** — Added `ttl` parameter to `enable_skill()` wrapper to support constructing naturally expiring grants for Scenario 03 expired grant verification.

**Hook Indexer Initialization Fix:**

Included in this release (may have been fixed in prior commits):
- Fixed hook indexer initialization for subprocess-based hook execution — `UserPromptSubmit` and `PreToolUse` hooks now initialize skill index in fresh subprocesses, preventing tool rejection errors after `enable_skill` due to empty indexer state.

## [0.2.0] — 2026-04-19

Phase 4 completion: observability, quality gates, and release polish. No
breaking runtime config changes; existing `data_dir`, `skills_dir`, and
`config/default_policy.yaml` continue to load as-is.

### Added

- **Audit event completeness.** All nine canonical event types
  (`skill.list`, `skill.read`, `skill.enable`, `skill.disable`,
  `tool.call`, `grant.expire`, `grant.revoke`, `stage.change`,
  `prompt.submit`) are now emitted consistently across `hook_handler`,
  `mcp_server`, and `grant_manager`. `grant.revoke` is a first-class
  event distinct from `skill.disable` and `grant.expire`.
- **Funnel metrics.** `SQLiteStore.funnel_counts(session_id=None,
  skill_id=None)` returns aggregated `shown → read → enable → tool_calls`
  counts backed by the audit log's existing `session_id` and
  `event_type` indexes.
- **Three-bucket miscall classification.** PreToolUse denies now carry
  a precise `error_bucket` in `detail`:
  - `wrong_skill_tool` — the tool belongs to an indexed skill that
    was not enabled,
  - `tool_not_available` — the tool is unknown or was stripped by
    `blocked_tools`/stage gating from an enabled skill,
  - `parameter_error` — recorded by PostToolUse when `tool_response`
    carries an `is_error` / `error` signal.
- **Optional Langfuse tracing.** `core/observability.py` wires a no-op
  `LangfuseTracer` by default. When the `observability` optional
  dependency is installed and `LANGFUSE_PUBLIC_KEY` is set, each
  session maps to a Langfuse trace and every audit event becomes a
  trace event. Misconfiguration and SDK failures never break the
  governance hot path.
- **Phase 4 E2E + boundary tests.** New
  `tests/functional/test_functional_phase4_scenarios.py` covers
  multi-skill concurrent enable, skill-disable isolation, and
  `max_ttl` cap enforcement at grant creation.
- **Performance micro-benchmarks.** `scripts/bench_phase4.py` reports
  median / p95 / max latency per hook and per MCP tool, plus
  skill-index cache hit rate. Results captured in
  `docs/perf_results.md`:
  - hooks p95 < 1 ms (target < 50 ms),
  - MCP tools p95 < 1 ms (target < 100 ms),
  - skill-index cache hit rate 99.5% (target > 95%).
- **Cache hit-rate counters.** `VersionedTTLCache` now tracks `hits`
  and `misses` so the benchmark — or any downstream observer — can
  report an actual hit rate.

### Changed

- `SQLiteStore.__init__` now accepts an optional `tracer` kwarg;
  `append_audit` forwards each event to `tracer.emit` when present.
  Existing callers that only pass `data_dir` are unaffected.
- `GovernanceRuntime` now carries a `tracer` attribute (defaults to a
  no-op `LangfuseTracer`), populated by `create_governance_runtime`.
- `docs/技术方案文档.md` §6 gains a §6.5 pointing at
  `docs/perf_results.md` for benchmark numbers.
- README "Current Status" and "Roadmap" sections updated to reflect
  the new tests/coverage/benchmarks baseline and the closed
  Layer 2 / Layer 3 milestones.

### Quality

- `ruff check src/ scripts/` — clean.
- `mypy --strict src/tool_governance` — 24 source files, no issues.
- Test coverage on `core/`, `storage/`, `hook_handler.py`,
  `mcp_server.py`, `bootstrap.py`: **92%** overall (every module ≥
  80%; `sqlite_store` and `state_manager` at 100%).
- Full test suite: **190 passed**, 0 failed (baseline was 104 at the
  end of Phase 3, 167 after the phase13-hardening and
  functional-harness archives).

### Fixed

- Nothing new — all Phase 13 drift fixes (D1–D8) landed in 0.1.0's
  tail and remain in place.

## [0.1.0] — 2026-04-16

Initial release — bootstrap of the Stagewise-Tool-Gate Claude Code plugin with
the Phase 1–3 runtime governance core: skill indexer, policy engine,
grant manager, tool rewriter, prompt composer, SQLite store, MCP
server, and hook orchestration.
