# Functional Test Plan — tool-governance-plugin

> Stage A skeleton. Living document — rollout status table updated after
> each phase lands. Companion artifacts in
> `openspec/changes/add-functional-test-plan/`.

## 1. Purpose

Provide a deterministic, local-fixture-driven functional test harness that
drives the plugin through its real entry points (`tg-mcp`, `tg-hook`) and
covers the 8-step governance pipeline plus Phase 1–3 hardening invariants
(D1–D8). Unblocks Phase 4 by letting future changes be validated end-to-end
without a live Claude Code host.

## 2. Scope

**In scope:**
- `mock_`-prefixed Skills fixtures under `tests/fixtures/skills/`.
- Local stdio mock MCP servers under `tests/fixtures/mcp/`.
- In-process functional tests driving `hook_handler` / `mcp_server`.
- Subprocess stdio tests driving `tg-hook` / `tg-mcp`.

**Out of scope:**
- Phase 4 work (Langfuse, funnel metrics, miscall bucketing, benchmarks).
- Replay / evaluation framework.
- Live Claude Code end-to-end tests.
- Any `src/tool_governance/` changes.

## 3. Fixture Inventory

### 3.1 Mock Skills (`tests/fixtures/skills/mock_*`)

| Fixture | Risk | Stages | `allowed_ops` | Purpose |
|---|---|---|---|---|
| `mock_readonly` | low | no | `search`, `read_file` | Happy path, auto-grant. |
| `mock_stageful` | medium | `analysis`, `execution` | `analyze`, `edit` | `change_stage` path, reason-required. |
| `mock_sensitive` | high | no | `run` | Approval-required / deny branch. |
| `mock_ttl` | low | no | `ping` | TTL-expiry path (create with `ttl=0`). |
| `mock_refreshable` | low | no | `noop` | Drop-in mid-test for `refresh_skills`. |
| `mock_malformed` | — | — | — | Invalid YAML → `_index_one` skip-with-warning. |
| `mock_oversized` | — | — | — | Size > 100 KB → skip-with-warning. |

### 3.2 Mock stdio MCP servers (`tests/fixtures/mcp/mock_*_stdio.py`)

| Server | Surface | Purpose |
|---|---|---|
| `mock_echo_stdio` | `echo(text)` | Baseline MCP handshake, `tools/list`. |
| `mock_stage_stdio` | Tools matching `mock_stageful` stage allowed_tools | Stage-path skeleton — kept for future subprocess tests; no smoke test currently drives it. |
| `mock_sensitive_stdio` | `dangerous(target)` | Deny-path over real stdio; backs `TestMockSensitiveStdioHandshake` + `TestNamespacedMcpDenyInSubprocess`. |

### 3.3 Policy fixtures (`tests/fixtures/policies/`)

| File | Semantics | Exercised by |
|---|---|---|
| `default.yaml` | `low=auto`, `medium=approval`, `high=approval`, empty `blocked_tools`, empty `skill_policies` | `test_functional_policy_fixtures.py` (sanity + low-auto + medium-ask + blocked_tools strip), `test_functional_policy_e2e.py` (E1 low full chain, E2 medium ask), `test_functional_policy_e2e_lifecycle.py` (E8 TTL) |
| `restrictive.yaml` | `blocked_tools: [mock_sensitive, mock_ping]` (skill-id + tool-name routes); `skill_policies.mock_readonly.approval_required=true`, `skill_policies.mock_stageful.require_reason=true` | `test_functional_policy_fixtures.py` (high deny + skill override + blocked tool strip), `test_functional_policy_e2e.py` (E3 deny, E5 skill override, E6 require_reason both branches), `test_functional_policy_e2e_lifecycle.py` (E7 change_stage, E9 revoke — both via inline derivatives) |

## 4. Isolation Rules

- Every functional test gets a fresh `tmp_path` for `GOVERNANCE_DATA_DIR`
  (per-test SQLite file).
- `skills_dir`: point at `tests/fixtures/skills/` for read-only tests;
  copy a subset into `tmp_path` for tests that mutate the tree.
- `session_id`: derive from `request.node.name` so audit queries never
  cross tests.
- In-process tests inject `GovernanceRuntime` into
  `hook_handler._runtime` / `mcp_server._runtime`; fixture teardown
  restores `None`.
- Subprocess tests pass paths via env
  (`GOVERNANCE_DATA_DIR` / `GOVERNANCE_SKILLS_DIR` / `GOVERNANCE_CONFIG_DIR` /
  `CLAUDE_SESSION_ID`) to the child.
- All env mutations go through `monkeypatch.setenv`.

## 5. Test Lanes

| Lane | Transport | Use for |
|---|---|---|
| **In-process** | direct calls on `handle_*` / `mcp_server.*` via `asyncio.run` | governance logic, state, audit ordering. Fast. |
| **Stdio subprocess** | `subprocess.Popen([sys.executable, script], stdin=PIPE, stdout=PIPE)` | JSON contract shape, env wiring, `mcp__<server>__<tool>` matching. |

## 6. Trace Matrix (Requirement → File → Scenario)

| Spec Requirement | Test file | Key scenarios |
|---|---|---|
| Mock Skills Fixture Directory | `test_happy_path.py` + fixture sanity test | `mock_*` prefix, axis coverage, malformed/oversized skip. |
| Local stdio Mock MCP Server Fixture | `test_stdio_mcp.py` | `tools/list` handshake, PreToolUse denies `mcp__mock_*`. |
| Core 8-Step Pipeline | `test_happy_path.py`, `test_stdio_hook.py` | Full pipeline, hook JSON shape. |
| Lifecycle & Interception | `test_deny_path.py`, `test_stage_path.py`, `test_ttl_path.py`, `test_refresh_path.py`, `test_revoke_path.py` | deny, stage, TTL, refresh single-scan, revoke→disable order. |
| MCP ↔ LangChain Parity | `test_parity.py` | Equivalent grants; unknown scope coerces on both paths. |

## 7. Priority Flows (implementation order)

1. happy → 2. deny → 3. stage → 4. ttl → 5. refresh → 6. revoke →
7. parity → 8. stdio contract tests.

## 8. Rollout Status

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Plan doc | **done** |
| Phase 2 | Fixtures (valid `mock_*` skills + malformed/oversized + sanity test) | **done** |
| Phase 3 | `_support/` helpers (runtime, events, audit, skills) | **done** |
| Phase 4 | In-process functional tests (7 files, 19 tests) | **done** |
| Phase 5 | Stdio harness + mock MCP servers (`mock_echo_stdio`, `mock_sensitive_stdio`; `mock_stage_stdio` skeleton retained) | **done** |
| Phase 6 | Stdio functional tests (`test_functional_stdio.py` + `test_functional_smoke_subprocess.py`) | **done** |
| Stage F | Policy fixtures + policy-sensitive helper (`tests/fixtures/policies/*.yaml`, `make_runtime(policy_file=)`, `test_functional_policy_fixtures.py`) | **done** (2026-04-18) |
| Stage G | Smoke subprocess lane (`test_functional_smoke_subprocess.py`: `tg-mcp` meta-tools + `mock_sensitive_stdio` + `tg-hook` event-shape) | **done** (2026-04-18) |
| Stage H | Mock E2E lane (`test_functional_policy_e2e.py` E1–E6, `test_functional_policy_e2e_lifecycle.py` E7–E9) | **done** (2026-04-18) |

## 9. Conventions

- All fixtures and tests use the `mock_` prefix to make intent obvious in
  logs and audit rows.
- Functional tests must not edit files under `src/tool_governance/`.
- Each phase should leave `python -m pytest -q` green.

## 10. How to run

For the full, step-by-step local self-test operator manual (venv setup,
per-flow commands, Linux/macOS + PowerShell, Claude Code plugin smoke,
failure-triage table), see [`docs/self_test_runbook.md`](../../docs/self_test_runbook.md).

**Subset (functional only, fastest feedback):**

```
python -m pytest tests/functional/ -q
```

**Full suite (regression guard):**

```
python -m pytest -q
```

**Single flow:**

```
python -m pytest tests/functional/test_functional_ttl.py -q
```

## 11. Coverage Summary (Stages A–H)

### Functional test files (new)

| File | Tests | Pipeline node(s) |
|---|---|---|
| `test_functional_happy_path.py` | 7 | SessionStart → list → read → enable → UserPromptSubmit → run_skill_action → PostToolUse |
| `test_functional_gating.py` | 4 | PreToolUse deny (+ meta-tool allow fast-path, `tool_not_available` audit, MCP-namespaced deny) |
| `test_functional_stage.py` | 1 | `change_stage` + `stage.change` audit |
| `test_functional_ttl.py` | 2 | TTL expiry blocks `run_skill_action`; UserPromptSubmit sweep emits `grant.expire` (not `grant.revoke`) |
| `test_functional_refresh.py` | 2 | `refresh_skills` visibility + single `build_index` call (D3) |
| `test_functional_revoke.py` | 2 | `disable_skill` → `active_tools` drop + audit order `grant.revoke` → `skill.disable` (D7) |
| `test_functional_entrypoint_parity.py` | 2 | MCP ↔ LangChain `enable_skill` parity + unknown-scope coercion (D6) |
| `test_functional_fixture_sanity.py` | 1 | Indexer skips `mock_malformed` / `mock_oversized`, keeps 5 valid mocks; all ids use `mock_` prefix |
| `test_functional_stdio.py` | 2 | `mock_echo_stdio` `tools/list` handshake; `tg-hook` SessionStart subprocess stdout contract |
| `test_functional_smoke_subprocess.py` | 5 | `tg-mcp` 8 meta-tools; `mock_sensitive_stdio` handshake; `tg-hook` UserPromptSubmit + PreToolUse deny + MCP-namespaced deny contracts |
| `test_functional_policy_fixtures.py` | 7 | `default.yaml` / `restrictive.yaml` reach `PolicyEngine`; low-auto / medium-ask / high-deny / blocked-tool strip / skill-override through real loader |
| `test_functional_policy_e2e.py` | 7 | E1 low-risk full chain; E2 medium ask; E3 high deny; E4 blocked_tool strip + PreToolUse deny; E5 skill override; E6 require_reason both branches |
| `test_functional_policy_e2e_lifecycle.py` | 3 | E7 `change_stage` under policy; E8 TTL sweep under policy; E9 revoke audit order under policy |

**Total: 45 functional tests.** Full suite: **167 passed**.

### Flows verified end-to-end (in-process lane)

1. Happy path: catalog injection → skill discovery → read SOP → auto-grant enable → per-turn context refresh → gated tool call → post-call writeback.
2. Deny path: non-allowlisted tool → PreToolUse deny with guidance `additionalContext`; meta-tools bypass gate; MCP-namespaced `mcp__<server>__<tool>` subject to same gate.
3. Stage path: medium-risk + reason → default stage tools → `change_stage` swaps tool set → audit row.
4. TTL path: expired grant blocks `run_skill_action`; per-turn sweep unloads skill + emits `grant.expire`.
5. Refresh path: new skill fixture visible only after `refresh_skills`; exactly one `build_index` per call.
6. Revoke path: explicit disable removes tools from `active_tools`; audit boundary `grant.revoke` → `skill.disable`.
7. Parity: MCP and LangChain wrappers produce equivalent Grants; both coerce unknown `scope` → `"session"`.
8. **Policy-sensitive E2E (Stage H):** every risk band (low/medium/high), `blocked_tools` (skill-id + tool-name routes), and `skill_policies` override path exercised through the real `bootstrap.load_policy` → `PolicyEngine` chain — no monkeypatch on `PolicyEngine.evaluate`.

### Mock skill fixtures

| Fixture | Used by |
|---|---|
| `mock_readonly` | happy path, gating, revoke, parity, policy E1 / E4 / E5 / E8 / E9 |
| `mock_stageful` | stage path, policy E2 / E6 / E7 |
| `mock_sensitive` | gating deny, policy E3 (`mock_dangerous` tool never enabled) |
| `mock_ttl` | TTL path, policy `TestBlockedToolsStripsActiveTools` (`mock_ping` blocked) |
| `mock_refreshable` | refresh path (dropped into tmp tree mid-test) |

### Mock stdio MCP servers

| Server | Purpose | Status |
|---|---|---|
| `mock_echo_stdio` | baseline MCP handshake fixture | **exercised** by `test_functional_stdio.py::TestMockEchoStdioHandshake` |
| `mock_sensitive_stdio` | deny-path handshake + namespaced deny | **exercised** by `test_functional_smoke_subprocess.py::TestMockSensitiveStdioHandshake` + `TestNamespacedMcpDenyInSubprocess` |
| `mock_stage_stdio` | tools matching `mock_stageful` stage allowed_tools | skeleton only (no subprocess test yet — see backlog) |

### Backlog (not yet covered)

- `mock_stage_stdio` deeper round-trip (subprocess `tools/list` + `tools/call` for the stage-matched tool names).
- Live-Claude-Code E2E (A12 Langfuse chain, A13 `/plugin install`) — explicitly out of scope for this change.
- Phase 4 work proper: Langfuse integration, funnel metrics, miscall bucketing, performance benchmarks.
