## Context

Phases 1–3 landed with `tests/test_integration.py` (122 passing) and
per-module unit tests. Those tests call handlers in-process with hand-built
state; nothing exercises the real stdio boundaries (`tg-mcp`, `tg-hook`) or
uses skills loaded from a cold directory scan. Phase 4 (Langfuse, funnel
metrics, benchmarks) is blocked behind a functional harness that can drive
the plugin deterministically without a live Claude Code host.

Source files consulted: `src/tool_governance/{mcp_server,hook_handler}.py`,
`core/{skill_indexer,tool_rewriter,prompt_composer}.py`,
`tests/test_integration.py`, `.mcp.json`, `hooks/hooks.json`.

## Goals / Non-Goals

**Goals:**
- Minimum-invasive test scaffolding — **zero production-code edits**.
- A fixture tree of `mock_`-prefixed skills covering the axes the governance
  engine branches on (risk, stages, `allowed_ops`, malformed, oversized).
- A small set of `mock_`-prefixed local stdio MCP server scripts that speak
  just enough MCP to be launched as pytest subprocess fixtures.
- Functional tests that drive both the Python layer (fast, deterministic) and
  the real stdio entry points (`tg-mcp`, `tg-hook`) end-to-end.
- Strong isolation: every test gets its own SQLite path, skills root, config
  dir, and session_id — no shared global state.
- Phased rollout inside the change so no single implementation turn balloons
  context.

**Non-Goals:**
- No rewrite of `mcp_server.py` / `hook_handler.py` / core modules.
- No Phase 4 work (Langfuse integration, funnel metrics, miscall-bucket
  analytics, benchmarks).
- No live-Claude-Code E2E, no `/plugin install` tests.
- No new runtime dependencies; test-only deps only if strictly necessary.
- No test against a real third-party MCP server.

## Decisions

### D1 — Test tree layout

```
tests/
  functional/
    __init__.py
    test_happy_path.py            # 8-step pipeline
    test_deny_path.py             # PreToolUse deny for non-allowlisted tool
    test_stage_path.py            # change_stage → active_tools delta
    test_ttl_path.py              # grant expiry reclamation
    test_refresh_path.py          # refresh_skills single-scan + visibility
    test_revoke_path.py           # disable_skill → revoke + audit ordering
    test_parity.py                # MCP vs LangChain enable_skill parity
    test_stdio_hook.py            # subprocess-driven tg-hook (stdin/stdout)
    test_stdio_mcp.py             # subprocess-driven tg-mcp (FastMCP stdio)
    _support/
      __init__.py
      runtime.py                  # tmp-dir runtime factory, hh._runtime injection
      stdio.py                    # subprocess lifecycle for tg-hook / tg-mcp / mock_* MCP
      events.py                   # canonical hook event JSON builders
      audit.py                    # audit-log query helpers
      skills.py                   # fixture-path resolver
  fixtures/
    skills/                       # mock_-prefixed SKILL.md tree
      mock_readonly/SKILL.md
      mock_stageful/SKILL.md
      mock_sensitive/SKILL.md
      mock_ttl/SKILL.md
      mock_refreshable/SKILL.md
      mock_malformed/SKILL.md     # intentionally broken YAML
      mock_oversized/SKILL.md     # > 100 KB sentinel
    mcp/
      mock_echo_stdio.py          # minimal FastMCP server, one echo tool
      mock_stage_stdio.py         # advertises tools that match mock_stageful
      mock_sensitive_stdio.py     # tools gated by high-risk skill
    policies/
      default.yaml                # low=auto / medium=reason / high=approval
      restrictive.yaml            # for deny-path variants
  functional/FUNCTIONAL_TEST_PLAN.md  # plan doc (living, updated per phase)
```

Rationale: a single `tests/functional/` root keeps the new surface
discoverable; `tests/fixtures/` sits next to it so both existing unit
tests and new functional tests can reuse fixtures without cross-tree
imports; `_support/` under `functional/` keeps helpers local to the new
suite (avoids leaking subprocess helpers into unit-test scope).

### D2 — Mock skills set (minimum viable)

| fixture | risk | stages | allowed_ops | purpose |
|---|---|---|---|---|
| `mock_readonly` | low | no | `search`, `read_file` | happy path, auto-grant |
| `mock_stageful` | medium | `analysis` + `execution` | `analyze`, `edit` | change_stage path, reason-required |
| `mock_sensitive` | high | no | `run` | approval-required branch, deny |
| `mock_ttl` | low | no | `ping` | TTL-expiry path (create with `ttl=0`) |
| `mock_refreshable` | low | no | `noop` | drop in mid-test to validate `refresh_skills` |
| `mock_malformed` | — | — | — | YAML error → `_index_one` skip-with-warning |
| `mock_oversized` | — | — | — | size > 100 KB → skip-with-warning |

All metadata `skill_id`s and tool names are `mock_*` so they never collide
with production tool names and show up cleanly in audit logs.

### D3 — Mock stdio MCP servers

| server | surface | purpose |
|---|---|---|
| `mock_echo_stdio` | one tool `mcp__mock_echo__echo` | baseline MCP handshake, `tools/list`, round-trip `tools/call` |
| `mock_stage_stdio` | tools matching `mock_stageful` stage allowed_tools | stage path over real stdio |
| `mock_sensitive_stdio` | tools gated by `mock_sensitive` | deny path over real stdio |

Each is a small Python script using the same `mcp.server.fastmcp.FastMCP`
stack as `mcp_server.py`, launched by `_support/stdio.py` via
`subprocess.Popen([sys.executable, <path>], stdin=PIPE, stdout=PIPE)`. A
pytest fixture yields a `Client` wrapper, and `finally` sends `terminate()`
+ `wait(timeout=2)` + `kill()` on hang. No network, no ports.

### D4 — Isolation model (per-test)

Each functional test gets:
- `tmp_path` for `GOVERNANCE_DATA_DIR` (fresh SQLite file per test).
- A per-test `skills_dir` — either pointing at `tests/fixtures/skills/` for
  read-only tests, or a copied subset in `tmp_path` for tests that mutate
  the tree (e.g. `mock_refreshable` drop-in).
- A per-test `config_dir` picking `default.yaml` or `restrictive.yaml`.
- A session_id derived from the test function name (e.g.
  `f"func-{request.node.name}"`) so audit queries never cross tests.
- For in-process tests: inject runtime into `hook_handler._runtime` /
  `mcp_server._runtime` (same pattern as existing `tests/test_integration.py`),
  clear in fixture teardown.
- For subprocess tests: pass paths via env (`GOVERNANCE_DATA_DIR`,
  `GOVERNANCE_SKILLS_DIR`, `GOVERNANCE_CONFIG_DIR`, `CLAUDE_SESSION_ID`) to
  the child; child runs the production entry-point script.

### D5 — Two test lanes (Python-layer vs stdio-layer)

| Lane | Transport | Speed | What it verifies | Files |
|---|---|---|---|---|
| **In-process** | direct function calls on `hook_handler.handle_*` and `mcp_server.*` (asyncio.run) | fast | governance logic, state transitions, audit records | most of `test_happy_path.py`, `test_deny_path.py`, `test_stage_path.py`, `test_ttl_path.py`, `test_refresh_path.py`, `test_revoke_path.py`, `test_parity.py` |
| **Stdio subprocess** | `tg-hook` reading JSON from stdin, `tg-mcp` speaking MCP over stdio | slower (1 process/test) | JSON contract shape, env-var wiring, meta-tool discoverability, mcp-name matching in PreToolUse | `test_stdio_hook.py`, `test_stdio_mcp.py` |

Two lanes let us keep the fast loop fast while still validating the contract
that Claude Code actually exercises.

### D6 — Phased implementation inside the change

Phases are separate sections of `tasks.md`; each is a self-contained
implementation turn:

1. **Plan doc** — `FUNCTIONAL_TEST_PLAN.md` (scope, matrix, fixture inventory,
   isolation rules).
2. **Fixtures** — all `mock_*` SKILL.md files + policy YAMLs.
3. **In-process helpers** — `_support/runtime.py`, `events.py`, `audit.py`.
4. **In-process tests** — happy/deny/stage/ttl/refresh/revoke/parity
   (one file per path).
5. **Stdio harness** — `_support/stdio.py` + mock MCP server scripts.
6. **Stdio tests** — `test_stdio_hook.py`, `test_stdio_mcp.py`.

Rollback per phase is `git revert` on that phase's commit; nothing here
touches production code.

### Test matrix (which path → which file → which requirement)

| Path | File | Spec requirement |
|---|---|---|
| happy | `test_happy_path.py` | Core 8-Step Pipeline |
| deny | `test_deny_path.py` | Lifecycle/Interception (PreToolUse deny) |
| stage | `test_stage_path.py` | Lifecycle/Interception (change_stage) |
| ttl | `test_ttl_path.py` | Lifecycle/Interception (TTL expiry, `grant.expire`) |
| refresh | `test_refresh_path.py` | Lifecycle/Interception (`refresh_skills` single-scan) |
| revoke | `test_revoke_path.py` | Lifecycle/Interception (revoke→disable ordering) |
| parity | `test_parity.py` | MCP ↔ LangChain parity |
| stdio | `test_stdio_hook.py`, `test_stdio_mcp.py` | Mock stdio MCP fixture + hook contract |

## Risks / Trade-offs

- **Subprocess flakiness** → mitigation: terminate+kill timeout, fail-fast on
  first hang, keep stdio tests small (one-roundtrip shape checks, not full
  pipelines). Pipelines stay on the in-process lane.
- **Fixture drift vs production skill format** → mitigation: the indexer is
  the only YAML parser; any schema change shows up as a unit-test
  regression on the indexer before we touch fixtures.
- **Test-tree grows too large in one commit** → mitigation: D6 phase split
  keeps each commit/PR bounded.
- **Meta-missing edge cases already covered by unit/integration tests** →
  functional suite intentionally does not duplicate them; it focuses on
  cross-module paths.
- **SQLite contention if tests share a data dir** → mitigation: `tmp_path`
  per test function, not per session. Accept the small I/O cost.
- **Env-var leakage between tests** → mitigation: all env mutations go
  through `monkeypatch.setenv`; `_runtime` singletons cleared in fixture
  teardown (same pattern as existing `test_integration.py`).

## Migration Plan

- No runtime migration — this change only adds files under `tests/`.
- After merge, `docs/dev_plan.md` §6 "Current Progress" gets a line noting
  the functional test harness landed before Phase 4 starts.
- Rollback: revert the change's commits; production code is untouched.

## Open Questions

- Does `FastMCP` stdio mode require any handshake beyond what the default
  client does? Confirm while implementing `_support/stdio.py`. If non-trivial,
  the stdio lane can shrink to "start server, send `tools/list`, assert
  response" and leave deeper round-trips to the in-process lane.
- Should policy fixtures live under `tests/fixtures/policies/` or inline
  in each test's `tmp_path`? Default: under fixtures dir for reuse;
  inline only when a test needs a one-off variant.

---

## Extension — Policy-driven smoke + mock E2E

> Added 2026-04-18 after the in-process and minimal stdio lanes shipped.
> Upgrades the suite to exercise `PolicyEngine` + `ToolRewriter` through
> real YAML fixtures (no monkey-patching of decisions) and adds a
> repo-internal E2E lane that drives the full SessionStart → PostToolUse
> chain.

### Context delta

- Existing `_support.runtime.make_runtime` writes an inline `default_policy.yaml`
  that is effectively a "policy-open" harness (low=auto, medium=reason,
  high=approval). That was sufficient to prove the lifecycle flows but
  cannot prove policy-sensitive behaviour — in particular, the
  restrictive branches (`denied`, global blocked tool, skill-specific
  override) are currently unexercised.
- Scope stays minimum-invasive: still **zero production-code edits**.
  Only additions are test helpers, fixtures, and new test files.

### Goals / non-goals (additive)

**Goals:**
- Load policy from real YAML fixtures through `bootstrap.load_policy`,
  same code path production uses — tests never patch `PolicyEngine.evaluate`.
- Cover at least 5 policy-sensitive E2E scenarios (see matrix §4 below).
- Broaden the smoke lane so every `mock_*_stdio` fixture and every
  `tg-hook` event-type has at least one contract-shape assertion.

**Non-goals:**
- No live Claude Code, no Langfuse, no benchmarks.
- No "policy-open" shortcut: tests MUST NOT use
  `monkeypatch.setattr(policy_engine, "evaluate", ...)` to satisfy an
  assertion. `skill_executor.dispatch` may still be stubbed because it
  is outside the governance decision path.
- No new `mock_*` skill types. The 5 existing mocks + the 2 skeletons
  plus a new `mock_sensitive_stdio` are the full surface.

### 1. Policy fixtures design

**Location:** `tests/fixtures/policies/` (answering the Open Question
§"Where should policy fixtures live" — dir beats inline for reuse).

#### `tests/fixtures/policies/default.yaml`

Baseline, slightly stricter than the current inline YAML so the **ask**
branch can be tested:

```yaml
default_risk_thresholds:
  low: auto
  medium: ask         # PolicyEngine treats unknown → auto; we need explicit "approval" to test the ask branch; see mapping note
  high: ask
default_ttl: 3600
default_scope: session
blocked_tools: []
skill_policies: {}
```

**Mapping note:** `PolicyEngine.evaluate` recognises three threshold
values — `"auto"`, `"reason"`, `"approval"`. The spec language "ask" is
an abstraction over "reason_required OR approval_required". To keep the
test matrix crisp we encode "ask" as `approval` in YAML — i.e. every
medium/high risk enable without a skill-specific override returns
`decision="approval_required"`. Scenarios that want the `"reason"`
branch (see #6 below) use a skill-specific `require_reason: true`
override instead of relying on the risk-level default. This avoids
overloading YAML strings that `PolicyEngine` does not recognise.

#### `tests/fixtures/policies/restrictive.yaml`

```yaml
default_risk_thresholds:
  low: auto
  medium: approval
  high: denied        # not a recognised PolicyEngine value — see translation below
default_ttl: 600
default_scope: turn
# Tool-name entries strip from active_tools via ToolRewriter; skill-id
# entries deny at enable_skill via PolicyEngine. `blocked_tools` is
# used by BOTH, so choose entries carefully.
blocked_tools:
  - mock_read          # strips the tool from active_tools even after a successful enable
skill_policies:
  mock_readonly:
    auto_grant: false
    require_reason: false
    approval_required: true   # skill-specific override: low-risk skill now needs approval
    max_ttl: 120
  mock_stageful:
    auto_grant: false
    require_reason: true      # override: test the "reason" branch explicitly
    approval_required: false
    max_ttl: 300
```

**Translation note:** `PolicyEngine` silently auto-grants any
unrecognised threshold (see the `else` branch at
`src/tool_governance/core/policy_engine.py:111`). To get an
unconditional deny for high-risk we cannot rely on `high: denied` in
the YAML — instead the test adds `mock_sensitive` to
`skill_policies` with `approval_required: true` OR adds
`mock_sensitive` to `blocked_tools` (which the policy engine treats as
a skill-id denylist). The design uses the `blocked_tools` route because
it matches the spec phrasing "high-risk deny under restrictive policy"
and produces a clean `decision="denied"` response. The YAML `high:
denied` line above is therefore documentation-only; the engine ignores
it.

**Alternative considered:** extend `PolicyEngine` to recognise
`"denied"` as a threshold. **Rejected** for this round: it would be a
production-code change, out of scope.

### 2. Test support changes

Extend `_support/runtime.py` with one new parameter, no new helper file:

```
def make_runtime(
    tmp_path,
    *,
    skills_dir=None,
    policy_yaml=DEFAULT_POLICY_YAML,   # existing — inline string
    policy_file=None,                  # NEW — path to a fixture YAML; wins over policy_yaml
):
```

When `policy_file` is provided, copy its contents into
`tmp_path/config/default_policy.yaml` so `bootstrap.load_policy` reads
the same text. No new abstraction — just the file-copy path.

Add a fixture-path resolver already present in `_support/runtime.py`:
`fixtures_policies_dir()` returns `tests/fixtures/policies/`.

### 3. Smoke matrix

**Goal:** every subprocess entry point has at least one minimal launch +
protocol-round-trip assertion. No policy sensitivity here — smoke is
"does it start and respond at all".

| # | Target | Transport | Assertion | Status before this extension |
|---|---|---|---|---|
| S1 | `mock_echo_stdio` | MCP stdio | `tools/list` includes `echo` | ✅ exists (`test_functional_stdio.py::TestMockEchoStdioHandshake`) |
| S2 | `mock_stage_stdio` | MCP stdio | `tools/list` includes `mock_read`, `mock_glob`, `mock_edit`, `mock_write` | **NEW** |
| S3 | `tg-mcp` | MCP stdio | `tools/list` includes the 8 meta-tools (`list_skills`, `read_skill`, `enable_skill`, `disable_skill`, `grant_status`, `run_skill_action`, `change_stage`, `refresh_skills`) | **NEW** |
| S4 | `tg-hook` | stdin JSON | `SessionStart` event → stdout is a single JSON object with `additionalContext` | ✅ exists |
| S5 | `tg-hook` | stdin JSON | `UserPromptSubmit` event → stdout single JSON object with `additionalContext` | **NEW** |
| S6 | `tg-hook` | stdin JSON | `PreToolUse` event (non-allowlisted tool) → stdout has `hookSpecificOutput.hookEventName == "PreToolUse"` and `permissionDecision == "deny"` | **NEW** |

All smoke tests land in `test_functional_stdio.py` (extend, don't split).

### 4. Mock E2E matrix (policy-sensitive)

**Rule:** every row drives the runtime with one of the two real YAML
fixtures. No row patches `PolicyEngine`. Each row exercises
SessionStart → (enable_skill or equivalent) → state/active_tools assertions
→ PreToolUse/run_skill_action → audit check.

| # | Scenario | Fixture skill | Policy | Key steps | Expected |
|---|---|---|---|---|---|
| E1 | Low-risk auto-allow | `mock_readonly` | `default.yaml` | SessionStart → `enable_skill(mock_readonly)` → `run_skill_action(mock_readonly, search)` (stub dispatch) | `granted=True`, `granted_by=auto`, `mock_read`+`mock_glob` in active_tools, dispatch called once, `skill.enable` audit with `decision="granted"` |
| E2 | Medium-risk ask / no auto-grant | `mock_stageful` | `default.yaml` | SessionStart → `enable_skill(mock_stageful)` without reason | `granted=False`, `decision="approval_required"`, `mock_read` NOT in active_tools, `skill.enable` audit with `decision="approval_required"` |
| E3 | High-risk deny under restrictive | `mock_sensitive` | `restrictive.yaml` (add `mock_sensitive` to `blocked_tools`) | `enable_skill(mock_sensitive, reason="x")` | `granted=False`, `decision="denied"`, audit `decision="denied"`, no Grant row in DB |
| E4 | Global blocked tool strips from active_tools | `mock_readonly` | `restrictive.yaml` (`blocked_tools: [mock_read]`) | enable ok (override makes it need approval — see E5; for E4 use a policy variant where `mock_readonly` is auto + `mock_read` blocked) → `run_skill_action` ok but `PreToolUse(mock_read)` denied | enable returns `granted=True`; active_tools does NOT contain `mock_read`; PreToolUse deny with `whitelist_violation` audit |
| E5 | Skill-specific override beats risk-level default | `mock_readonly` | `restrictive.yaml` (`skill_policies.mock_readonly.approval_required=true`) | `enable_skill(mock_readonly)` | Low-risk skill returns `granted=False`, `decision="approval_required"` — override beats `low: auto` default |
| E6 | Skill-specific `require_reason` override | `mock_stageful` | `restrictive.yaml` (`skill_policies.mock_stageful.require_reason=true`) | `enable_skill(mock_stageful)` w/o reason vs with reason | Without reason: `granted=False`, `decision="reason_required"`. With reason: `granted=True`, `decision="auto"`, reason recorded on Grant |

E4 and E5 use **different** restrictive YAMLs because their `mock_readonly`
intent conflicts (E4 wants low+auto, E5 wants low+override-to-approval).
Either split into `restrictive_blocked_tool.yaml` and
`restrictive_override.yaml`, or — cleaner — parametrise the test with
a small inline delta on top of the base `restrictive.yaml`. **Decision:**
keep one `restrictive.yaml` matching E5 (the named canonical fixture);
E4 uses an inline derivative written to `tmp_path` by the test. Matches
existing pattern of inline-policy for one-off variants.

All E2E tests land in a new `test_functional_policy_e2e.py`. One class
per scenario; teardown via `runtime_context`.

### 5. Risks / trade-offs (additive)

- **Risk:** policy YAML drift vs `PolicyEngine` value set. Mitigation:
  the mapping note above documents the exact string-level contract, and
  S3/E2/E3 tests assert the decision string (`approval_required`,
  `denied`) rather than inferring from state alone.
- **Risk:** E4 using an inline derivative could drift from
  `restrictive.yaml`. Mitigation: helper loads the base YAML, mutates
  one key, writes to `tmp_path` — single line delta, easy to audit.
- **Risk:** S3 (`tg-mcp` meta-tools listing) may be slow due to MCP
  SDK handshake overhead × 8 tools. Mitigation: single `tools/list`
  call, assert set equality, no per-tool round-trips.
- **Trade-off:** accepting that `blocked_tools` is overloaded (skill-id
  denylist in `PolicyEngine`, tool-name denylist in `ToolRewriter`) is
  a pre-existing production semantic we do not fix here. Tests call
  this out explicitly; `docs/technical_design.md` can be updated in a
  separate change if desired.

### 6. Implementation order

1. **Policy fixtures.** Write `tests/fixtures/policies/default.yaml`
   and `restrictive.yaml`. Add `fixtures_policies_dir()` +
   `policy_file=` parameter to `_support/runtime.make_runtime`.
2. **Smoke matrix backfill.** Extend `test_functional_stdio.py` with
   S2, S3, S5, S6 (4 new tests). Kill on timeout if FastMCP hangs.
3. **Mock E2E matrix.** New file `test_functional_policy_e2e.py` with
   one class per E1–E6. Reuse `runtime_context(tmp_path, policy_file=...)`.
4. **Docs sync.** Update `tests/functional/README.md` coverage table
   and `docs/self_test_runbook.md` §3, §6 with the new file names.
5. **Tasks.md.** Add Phase 7 section with the above as a tick-list;
   do NOT re-number existing phases.

Rollback: revert the commit(s) in phase order. No production code
touched, so rollback is trivial.

### 7. Open questions (additive)

- **Q1:** Does `PolicyEngine` need a first-class `"denied"` threshold?
  Current workaround (blocked_tools as skill-id denylist) works but is
  cryptic. Defer to a follow-up change.
- **Q2:** Should the smoke lane add a `PostToolUse` stdout-shape test?
  Currently only SessionStart/UserPromptSubmit/PreToolUse are listed
  (S4–S6). PostToolUse returns `{}` and carries no visible contract —
  adding a test would over-specify. Decision: skip.
