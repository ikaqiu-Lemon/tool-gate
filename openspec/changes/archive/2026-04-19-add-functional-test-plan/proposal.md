## Why

Phases 1–3 shipped with unit tests and a single `tests/test_integration.py` that
exercises core modules in-process. There is **no documented, executable
functional test plan** that drives the plugin the way Claude Code does: stdio
MCP traffic, hook events over stdin/stdout, skills loaded from disk. The Phase
1–3 hardening round surfaced several behaviours (D1/D2/D3/D6/D7) that unit
tests missed and integration tests only partly covered. Before Phase 4 adds
Langfuse, funnel metrics, and benchmarks, we need a deterministic functional
harness so future changes can be validated end-to-end without hand testing in
Claude Code.

## What Changes

- Add a **functional test plan document** under `tests/functional/` (or
  similar) describing scope, fixture strategy, trace matrix of requirement →
  acceptance criterion → test, and phased rollout.
- Add a set of **`mock_`-prefixed Skills fixtures** under
  `tests/functional/fixtures/skills/` covering the axes the governance engine
  cares about (low/medium/high risk, with/without stages, with/without
  `allowed_ops`, malformed frontmatter, oversized files). These are fixtures,
  **not** real skills — the `mock_` prefix keeps them out of the shipped
  `skills/` directory and makes intent obvious in audit logs.
- Add **local stdio mock MCP fixtures** (`mock_` prefix) that speak the MCP
  stdio protocol just enough to stand in for third-party MCP servers under
  test, so `run_skill_action` dispatch, PreToolUse interception, and MCP tool
  name matching (`mcp__<server>__<tool>`) can be exercised without network or
  real external MCP servers.
- Add **functional tests** that drive `mcp_server.py` and `hook_handler.py`
  via their real entry points (stdio / stdin-JSON), covering the 8-step core
  pipeline, the Phase 1–3 hardening invariants (D1–D8), and the acceptance
  items A1–A11 from `docs/requirements.md` that are testable without a live
  Claude Code host.
- **Phased rollout** inside this change: plan doc → fixtures → stdio harness →
  pipeline tests → hardening-invariant tests → A-matrix coverage pass. Each
  phase is a tasks.md section so context does not balloon.

## Capabilities

### New Capabilities
- `functional-test-harness`: deterministic, local-fixture-driven functional
  test suite for the tool-governance plugin, including the plan document,
  `mock_` skills and MCP fixtures, a stdio-driven harness for `mcp_server`
  and `hook_handler`, and the test cases that exercise the 8-step core
  pipeline plus Phase 1–3 hardening invariants.

### Modified Capabilities
- _(none — no shipped requirements change; this adds a test surface only.)_

## Impact

- **Code**: adds `tests/functional/` (plan, fixtures, harness, tests). No
  edits to `src/tool_governance/` are required to complete this change; any
  real bug uncovered while writing tests is tracked as a separate follow-up,
  not folded in here.
- **Dependencies**: pytest + pytest-asyncio (already present). May add
  `pytest` plugin(s) for stdio subprocess fixtures if needed; no new runtime
  deps.
- **Docs**: `docs/dev_plan.md` §6 "Current Progress" updated on archive to
  note the functional test harness landed before Phase 4.
- **Out of scope** (explicitly deferred):
  - Phase 4 work: Langfuse integration, funnel metrics implementation,
    miscall-bucket analytics, performance benchmarking.
  - Replay/evaluation framework (F18).
  - Live-Claude-Code end-to-end tests (A12 Langfuse chain, A13 directory
    structure via `/plugin install`) — these require a running host and are
    not deterministic in CI.
  - Any architectural rewrite of `mcp_server.py` / `hook_handler.py`.
  - Real third-party MCP servers; we only mock the stdio surface we need.

### Why `mock_` Skills + local stdio mock MCP (not real ones)

- **Determinism**: real skills and real MCP servers drift; fixtures frozen
  under `tests/functional/fixtures/` give reproducible inputs across CI runs
  and developer machines.
- **Axis coverage**: we need malformed frontmatter, oversized files,
  stage/no-stage, risk-level variants — none of which the shipped governance
  skill exercises. Purpose-built fixtures cover the axes cleanly.
- **Isolation**: the `mock_` prefix makes it impossible to confuse a fixture
  with a shipped skill in logs, audit records, or an accidentally-loaded
  skills directory.
- **No external deps**: local stdio mock MCP servers let us exercise
  `mcp__<server>__<tool>` name matching and PreToolUse interception without
  network access, third-party binaries, or auth.

### Why phased implementation

The full suite (plan + fixtures + harness + tests) would overflow a single
implementation turn. Splitting into phases — plan doc first, then fixtures,
then harness, then tests grouped by concern — keeps each turn's context
bounded, lets the plan doc act as the contract for later phases, and matches
how the Phase 1–3 hardening round was executed (Stages A/B/C/D).
