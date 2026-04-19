# Changelog

All notable changes to Tool-Gate are recorded in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - `whitelist_violation` — the tool is unknown or was stripped by
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

Initial release — bootstrap of the Tool-Gate Claude Code plugin with
the Phase 1–3 runtime governance core: skill indexer, policy engine,
grant manager, tool rewriter, prompt composer, SQLite store, MCP
server, and hook orchestration.
