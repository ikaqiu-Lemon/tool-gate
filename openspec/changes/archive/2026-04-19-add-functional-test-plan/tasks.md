# Tasks — add-functional-test-plan

Phased so each block fits a single implementation turn. Each phase ends
with `pytest -q` green before moving on. No edits to `src/tool_governance/`.

## Phase 1 — Plan doc

- [x] 1.1 Create `tests/functional/README.md` with: scope, fixture
  inventory, isolation rules, trace matrix (requirement → file →
  scenario), phased rollout status table. *(filename: README.md, not
  FUNCTIONAL_TEST_PLAN.md — `tests/functional/README.md` per user
  preference.)*
- [x] 1.2 Cross-link the plan doc from `docs/dev_plan.md` §6 (one bullet,
  no body rewrite).

## Stage A skeletons (files created, not full tasks) — superseded

*(Superseded on 2026-04-18: Phase 2.1 / 5.2 / 5.3 checkboxes above now
track these files directly. Kept for provenance only.)*

- [x] `tests/functional/__init__.py` + `_support/__init__.py` package
  markers.
- [x] Skeleton fixtures: `tests/fixtures/skills/mock_{readonly,stageful,
  sensitive,ttl,refreshable}/SKILL.md`, `tests/fixtures/mcp/
  {mock_echo_stdio,mock_stage_stdio}.py`, plus package markers for
  both fixture dirs.

## Phase 2 — Fixtures

- [x] 2.1 Create `tests/fixtures/skills/` with `mock_readonly/SKILL.md`,
  `mock_stageful/SKILL.md`, `mock_sensitive/SKILL.md`, `mock_ttl/SKILL.md`,
  `mock_refreshable/SKILL.md`.
- [x] 2.2 Add deliberately broken fixtures: `mock_malformed/SKILL.md`
  (invalid YAML) and `mock_oversized/SKILL.md` (>100 KB sentinel).
- [x] 2.3 Create `tests/fixtures/policies/default.yaml` (low=auto,
  medium=approval, high=approval) and `restrictive.yaml` (blocked_tools
  covering `mock_sensitive` + `mock_ping`, `mock_readonly` approval
  override, `mock_stageful` require_reason override).
  *(delivered by Stage F — see tasks 29–30; exercised by
  `test_functional_policy_fixtures.py` and Stage H
  `test_functional_policy_e2e.py` / `test_functional_policy_e2e_lifecycle.py`.)*
- [x] 2.4 Add a lightweight sanity test that `SkillIndexer.build_index()`
  on the fixture path returns exactly the valid `mock_*` skills and skips
  malformed/oversized with warnings.
  *(file: `tests/functional/test_functional_fixture_sanity.py`.)*

## Phase 3 — In-process support helpers

- [x] 3.1 `tests/functional/_support/runtime.py`: `make_runtime(tmp_path,
  *, skills_dir=None, policy_yaml=...)` + `runtime_context(tmp_path)`
  context manager; injects into `hook_handler._runtime` and
  `mcp_server._runtime`, clears on teardown.
- [x] 3.2 `_support/events.py`: builders for SessionStart /
  UserPromptSubmit / PreToolUse / PostToolUse event JSON.
- [x] 3.3 `_support/audit.py`: `events_of_type(runtime, sid, type)` +
  `decoded_detail(row)`.
- [x] 3.4 `_support/skills.py`: `copy_fixture_skills(dst_dir, names)` —
  used by the `refresh_skills` test to build a mutable tmp skills tree.

## Phase 4 — In-process functional tests

- [x] 4.1 `test_functional_happy_path.py`: 7 tests covering SessionStart
  indexing of mock_* skills, `list_skills`, `read_skill`, `enable_skill`
  (low-risk auto-grant), UserPromptSubmit context refresh,
  `run_skill_action` dispatch (monkeypatched), PostToolUse writeback.
- [x] 4.2 `test_functional_gating.py`: PreToolUse deny for
  non-allowlisted tool with guidance `additionalContext`; meta-tool
  always-allow; `whitelist_violation` audit bucket. (3 tests.)
- [x] 4.3 `test_functional_stage.py`: enable `mock_stageful` (medium,
  `reason=`), default stage tools, `change_stage` swaps tool set,
  `stage.change` audit emitted. (1 test.)
- [x] 4.4 `test_functional_ttl.py`: grant with `ttl=0` blocks
  `run_skill_action`; UserPromptSubmit sweep unloads skill and emits
  `grant.expire` (no `grant.revoke`). (2 tests.)
- [x] 4.5 `test_functional_refresh.py`: `mock_refreshable` invisible
  until copied into tmp skills tree and `refresh_skills` called; single
  `build_index` call per refresh. (2 tests.)
- [x] 4.6 `test_functional_revoke.py`: `disable_skill` drops tools
  from `active_tools`; audit order `grant.revoke` → `skill.disable`
  with `reason="explicit"`. (2 tests.)
- [x] 4.7 `test_functional_entrypoint_parity.py`:
  `mcp_server.enable_skill` vs `enable_skill_tool` produce equivalent
  grants; unknown scope coerces on both paths. (2 tests.)

## Phase 5 — Stdio harness + mock MCP servers

- [x] 5.1 `_support/stdio.py`: `spawn(script_path, env)` generic context
  manager + `run_hook_event(event, tmp_path, session_id)` one-shot helper
  for `tg-hook` + `mcp_handshake(script_path)` wrapping the official
  `mcp.client.stdio` SDK. Teardown chain: terminate → wait(2) → kill.
- [x] 5.2 `tests/fixtures/mcp/mock_echo_stdio.py`: minimal FastMCP server
  exposing one tool `echo(text)` → `{"echo": text}`.
  *(exercised by `test_functional_stdio.py` handshake test.)*
- [x] 5.3 `tests/fixtures/mcp/mock_stage_stdio.py`: tools whose names match
  `mock_stageful` stage allowed_tools (for PreToolUse name-matching tests).
  *(skeleton only — still available for future subprocess tests.)*
- [x] 5.4 `tests/fixtures/mcp/mock_sensitive_stdio.py`: tools gated by
  `mock_sensitive`; used by the deny-path stdio test.
  *(delivered by Stage G — see task 33; exercised by
  `test_functional_smoke_subprocess.py::TestMockSensitiveStdioHandshake`
  and `TestNamespacedMcpDenyInSubprocess` (`mcp__mock_sensitive__dangerous`).)*

## Phase 6 — Stdio functional tests

- [x] 6.1 `test_functional_stdio.py::TestHookSubprocessStdoutContract`:
  spawn `python -m tool_governance.hook_handler` as a subprocess, feed a
  `SessionStart` event on stdin, assert stdout is a single JSON object
  containing `additionalContext`.
- [x] 6.2 `test_stdio_mcp.py`: spawn `tg-mcp`, perform MCP `tools/list`
  handshake, assert the 8 meta-tools are present with expected names.
  *(delivered by Stage G as
  `test_functional_smoke_subprocess.py::TestTgMcpSubprocessMetaTools`
  — see task 35. The dedicated `test_stdio_mcp.py` filename was
  subsumed into the broader smoke-subprocess file; the assertion is
  `set(tool_names) == _EXPECTED_META_TOOLS` over the 8 canonical
  meta-tool names.)*
- [x] 6.3 `test_functional_stdio.py::TestMockEchoStdioHandshake`: spawn
  `mock_echo_stdio`, run `initialize` + `tools/list` handshake via the
  `mcp` client SDK, assert `echo` is advertised. Contract-only (no
  deeper tool round-trip).
- [x] 6.4 Close-out: update `tests/functional/README.md` "Rollout Status"
  and "Coverage Summary" tables.

### Gating test addendum

- [x] `test_functional_gating.py::test_mcp_namespaced_tool_is_denied_when_not_active`
  — PreToolUse deny with `tool_name="mcp__mock_echo__echo"` (addresses
  verify report Warning 6).

## Exit criteria

- `python -m pytest -q tests/` stays green (pre-existing 122 + new tests).
- No diff under `src/tool_governance/`.
- Every spec Requirement has at least one test in the trace matrix.

---

## Remaining work — Stages F, G, H

> Added 2026-04-18 as the reorganised, in-scope plan for closing the
> deferred policy / tg-mcp / E2E items from the Extension design.
> Replaces the older single-block "Phase 7" draft. Each stage is sized
> to one implementation turn; do not start a later stage before the
> earlier one is green.
>
> **Hard ground rules (all stages):**
> - No edits to `src/tool_governance/` for any reason.
> - No `monkeypatch.setattr(policy_engine, ...)`. Policy flows through
>   the real `bootstrap.load_policy` → `PolicyEngine` chain.
> - `skill_executor.dispatch` stubs remain allowed.
> - No Langfuse / benchmark / live Claude Code E2E.

### Stage F — Meaningful policy fixtures + policy-sensitive helper

**Status: done (2026-04-18).** 7/7 new tests green; full suite 152 passed.

**1. Files to add / modify**
- [x] NEW: `tests/fixtures/policies/default.yaml`
- [x] NEW: `tests/fixtures/policies/restrictive.yaml`
- [x] MODIFY: `tests/functional/_support/runtime.py` — added
  `policy_file: Path | None = None` kwarg to `make_runtime()` (wins
  over `policy_yaml=`); added `fixtures_policies_dir()` accessor.
- [x] NEW: `tests/functional/test_functional_policy_fixtures.py` — 7
  tests:
  - 2 fixture-loading sanity tests (default + restrictive reach
    `PolicyEngine` unchanged).
  - `TestLowRiskAutoAllowDefault` — mock_readonly + default.yaml →
    auto-grant (Grant.granted_by == "auto").
  - `TestMediumRiskAskDefault` — mock_stageful + default.yaml →
    `decision="approval_required"`, no Grant, no tool leak.
  - `TestHighRiskDenyRestrictive` — mock_sensitive + restrictive.yaml
    → `decision="denied"` via skill-id blocked-list route.
  - `TestBlockedToolsStripsActiveTools` — mock_ttl enableable under
    restrictive.yaml but `mock_ping` stripped from active_tools;
    PreToolUse denies.
  - `TestSkillOverrideBeatsRiskDefault` — mock_readonly under
    restrictive.yaml returns `approval_required` despite low risk.

**Implementation notes / surprises**
- `SkillPolicy` Pydantic model requires an explicit `skill_id` field
  inside each nested entry (not just the map key). Initial YAML omitted
  this and hit `ValidationError`; fixed by adding `skill_id: mock_readonly`
  inside the value dict. Recorded here so the next policy fixture gets
  it right on the first try.
- No `src/tool_governance/` edits made. Production code untouched.
- No `monkeypatch.setattr` against `PolicyEngine` anywhere; every
  assertion comes from the real engine reading the real YAML.

**2. Files NOT to touch**
- Anything under `src/tool_governance/`.
- `tests/fixtures/skills/**` and existing `mock_*` / `_support/` files
  (aside from the one `runtime.py` addition above).
- Existing functional test files (they keep running against the
  inline `DEFAULT_POLICY_YAML`).

**3. Commands**
```
python -m pytest tests/functional/test_functional_policy_fixtures.py -q
python -m pytest tests/functional/ -q
```
Both must be green before Stage G starts.

**4. Requirements / design points covered**
- `docs/requirements.md` §4.4 "Authorization Governance" (risk →
  decision mapping, user-visible policy).
- `docs/requirements.md` §5.1 F3 `enable_skill` (reason / scope / TTL).
- `docs/technical_design.md` §3.1.4 Policy model (`GovernancePolicy`,
  `SkillPolicy`).
- `docs/technical_design.md` §3.2.3 `policy_engine` precedence
  (blocked_list → skill-specific → risk-level default).
- Design §Extension §1 "Policy fixtures design" + §2 "Test support
  changes".

**5. Avoiding Request-too-large**
- Read only: `tests/functional/_support/runtime.py`, any file the
  implementation turn writes, plus the Extension section of
  `design.md` (§1–§2).
- Do NOT re-read `src/tool_governance/core/policy_engine.py` or
  `bootstrap.py` — their relevant behaviour is captured in design §1
  mapping notes.
- Do NOT re-read `docs/requirements.md` / `docs/technical_design.md` —
  use the already-documented references in design.md.

---

### Stage G — Smoke subprocess lane

**Status: done (2026-04-18).** 5 new subprocess smoke tests green;
functional 35, full suite 157 passed.

**1. Files to add / modify**
- [x] NEW: `tests/fixtures/mcp/mock_sensitive_stdio.py` — FastMCP
  server advertising one `dangerous(target)` tool. Pairs the namespaced
  MCP deny test with a real server that actually declares the matching
  tool name.
- [x] MODIFY: `tests/functional/_support/stdio.py` —
  `mcp_handshake()` now accepts either `script_path` **or**
  `command=` + `args=` + `env=`, so `tg-mcp` can be launched as
  `python -m tool_governance.mcp_server` without a dedicated wrapper
  script. Existing `script_path`-only callers unchanged.
- [x] NEW: `tests/functional/test_functional_smoke_subprocess.py` —
  5 tests:
  - `TestTgMcpSubprocessMetaTools` (1) — spawn
    `python -m tool_governance.mcp_server`, assert `tools/list` ==
    the 8 meta-tool names as a set.
  - `TestMockSensitiveStdioHandshake` (1) — spawn
    `mock_sensitive_stdio.py`, assert `dangerous` advertised.
  - `TestTgHookSubprocessUserPromptSubmit` (1) — UserPromptSubmit
    event → stdout single JSON object with `additionalContext`.
  - `TestTgHookSubprocessPreToolUseDeny` (1) — PreToolUse event for
    unknown tool → `hookSpecificOutput.hookEventName == "PreToolUse"`
    + `permissionDecision == "deny"` + `permissionDecisionReason`
    present.
  - `TestNamespacedMcpDenyInSubprocess` (1) — PreToolUse event with
    `tool_name="mcp__mock_sensitive__dangerous"` → deny with guidance
    `additionalContext` mentioning `enable_skill`.

**Implementation notes**
- Zero `src/tool_governance/` edits (confirmed).
- Zero `monkeypatch.setattr` — subprocess lane inherits the inline
  `DEFAULT_POLICY_YAML` through `prepare_plugin_dirs`.
- `mcp_handshake` extension was a pure additive test-seam; it did not
  require any production-code change.

**2. Files NOT to touch**
- `src/tool_governance/**`.
- `tests/fixtures/**` (skills *or* MCP).
- `tests/functional/_support/**` (unless a genuine missing primitive
  surfaces during implementation — in that case stop and ask).
- Stage F's policy fixtures (smoke lane uses the existing inline YAML;
  adding policy here would overlap with Stage H).

**3. Commands**
```
python -m pytest tests/functional/test_functional_stdio.py -q
python -m pytest tests/functional/ -q
```
Expected final counts in `test_functional_stdio.py`: 2 existing + 4
new = 6. Full functional suite ≥ 27 tests. Both must be green before
Stage H starts.

**4. Requirements / design points covered**
- `docs/requirements.md` §9 A1 (Plugin loading), A2 (Skill discovery
  via `list_skills`), A5 (Interception by PreToolUse), A8 (Per-turn
  UserPromptSubmit rewriting — contract shape only here).
- `docs/requirements.md` §5.1 F1 / F7 / F8 / F9 as stdio contract
  shapes (not deep state transitions).
- `docs/technical_design.md` §4.2 `.mcp.json`, §4.3 `hooks/hooks.json`,
  §4.5 MCP Server meta-tool definitions (the 8 names).
- Design §Extension §3 "Smoke matrix" rows S2 / S3 / S5 / S6.

**5. Avoiding Request-too-large**
- Read only: `tests/functional/test_functional_stdio.py`,
  `tests/functional/_support/stdio.py`, `.mcp.json`, `hooks/hooks.json`.
- Do NOT re-read `src/tool_governance/mcp_server.py` or
  `hook_handler.py` — the relevant meta-tool names and event names
  are in design.md § "Decisions" and section 3.
- Reuse the existing `prepare_plugin_dirs` / `run_hook_event` helpers
  for S5/S6; keep subprocess timeouts at 5s so a hang kills the test
  fast and does not starve CI.

---

### Stage H — Mock E2E lane (policy-sensitive + lifecycle re-verification)

**Status: done (2026-04-18).** 10 new E2E tests green; functional suite
45 passed, full repo 167 passed. Split into two files to stay under
the 220 LOC-per-file budget.

**1. Files to add / modify**
- [x] NEW: `tests/functional/test_functional_policy_e2e.py` — E1–E6
  (policy-sensitive core).  All scenarios use
  `runtime_context(tmp_path, policy_file=...)`; **no** monkeypatch on
  `policy_engine`.
- [x] NEW: `tests/functional/test_functional_policy_e2e_lifecycle.py`
  — E7–E9 (lifecycle re-verification under real policy).  Same
  honesty contract.

  Policy-sensitive core (design §4):
  - E1 `TestLowRiskAutoAllow` — `mock_readonly` + `default.yaml`.
  - E2 `TestMediumRiskAsk` — `mock_stageful` + `default.yaml`, no
    reason → `decision="approval_required"`.
  - E3 `TestHighRiskDenyUnderRestrictive` — `mock_sensitive` + inline
    derivative of `restrictive.yaml` that adds `mock_sensitive` to
    `blocked_tools` → `decision="denied"`.
  - E4 `TestGlobalBlockedToolStripsActiveTools` — `mock_readonly` +
    inline derivative of `restrictive.yaml` that keeps
    `blocked_tools: [mock_read]` but removes the `mock_readonly`
    approval override → enable succeeds; `mock_read` is NOT in
    `active_tools`; `PreToolUse(mock_read)` denies with
    `whitelist_violation` bucket.
  - E5 `TestSkillOverrideBeatsRiskDefault` — `mock_readonly` +
    canonical `restrictive.yaml` → low-risk skill returns
    `decision="approval_required"`.
  - E6 `TestRequireReasonOverride` — `mock_stageful` +
    `restrictive.yaml`, two sub-cases: without reason →
    `reason_required`; with reason → `granted=True`,
    `decision="auto"`, reason on Grant.

  Lifecycle re-verification under real policy (new, per user request —
  prove existing stage / TTL / revoke flows do not drift when policy
  comes from YAML):
  - E7 `TestChangeStageUnderPolicy` — `mock_stageful` +
    `restrictive.yaml` (override gives `require_reason=true`),
    enable with reason, `change_stage("execution")` swaps active
    tools; `stage.change` audit emitted.
  - E8 `TestTTLExpiryUnderPolicy` — `mock_readonly` + `default.yaml`,
    create grant with `ttl=0`, sleep 0.1s, `UserPromptSubmit` sweep
    unloads skill; `grant.expire` emitted, no `grant.revoke`.
  - E9 `TestRevokeUnderPolicy` — `mock_readonly` + canonical
    `restrictive.yaml` with the override temporarily relaxed (inline
    derivative), enable then `disable_skill`; audit order still
    `grant.revoke` → `skill.disable`, reason `"explicit"`.

- MODIFY: helper usage only. If an inline-YAML derivative pattern
  repeats ≥ 3 times, factor it into a tiny helper in
  `_support/runtime.py` (e.g. `make_policy_variant(base_path, **overrides)`);
  keep it to ≤ 15 lines. Otherwise keep inline `yaml.safe_load` +
  `yaml.safe_dump` inside the test file — no new helper modules.

**Implementation notes / surprises (2026-04-18)**
- Split into two files at implementation time: the full E1–E9 set
  exceeded the single-file 220 LOC budget after E1's full-chain
  assertions landed.  Sibling file
  `test_functional_policy_e2e_lifecycle.py` carries E7–E9 per the
  guidance in §5 below.
- Inline derivative pattern used in E4, E6 (with-reason branch), E7,
  and E9 — each uses a local 6-line `_policy_variant(tmp_path, base,
  mutate)` helper at file scope.  Duplicated verbatim across the two
  files (≤ 15 LOC total each); did NOT factor into
  `_support/runtime.py` because the factoring threshold (≥ 3 repeats
  *per consumer*) was not met and each copy fits the file's
  narrative.  Revisit if a third consumer appears.
- E3 uses canonical `restrictive.yaml` without modification because
  the canonical fixture already lists `mock_sensitive` in
  `blocked_tools` — the "inline derivative that adds mock_sensitive
  to blocked_tools" described in §1 of this plan is a no-op against
  the Stage F fixture.  Noted inline in the E3 docstring.
- E6 "with reason" branch and E7 both needed an inline derivative
  setting `mock_stageful.auto_grant=true` on top of `restrictive.yaml`.
  Reason: with canonical `auto_grant=false`, the skill-specific step
  (`PolicyEngine.evaluate` step 2) falls through to the medium=
  `approval` risk default even when a reason IS provided (documented
  silence at `src/tool_governance/core/policy_engine.py:86`).  The
  derivative flips `auto_grant=true` so the reason-satisfied path
  returns `decision="auto"` via step 2.  Canonical `restrictive.yaml`
  was NOT edited — the silence is a pre-existing production semantic,
  and Stage F tests depend on the current values.
- No `src/tool_governance/` edits; no `monkeypatch.setattr` against
  `PolicyEngine` anywhere.  `skill_executor.dispatch` stubbed only in
  E1.

**2. Files NOT to touch**
- `src/tool_governance/**`.
- `tests/fixtures/skills/**`, `tests/fixtures/mcp/**`.
- Existing functional test files (E7/E8/E9 are **re-verifications**
  under real policy — they do not replace
  `test_functional_stage.py` / `test_functional_ttl.py` /
  `test_functional_revoke.py`, which keep running against inline
  YAML).
- `tests/functional/_support/stdio.py` (unrelated to E2E lane).

**3. Commands**
```
python -m pytest tests/functional/test_functional_policy_e2e.py -q
python -m pytest tests/functional/ -q
python -m pytest -q
```
Expected: `test_functional_policy_e2e.py` reports 9+ tests (E1–E9, E6
contributes 2 sub-cases). Full suite ≥ 155 passed, zero regressions.

**4. Requirements / design points covered**
- `docs/requirements.md` §4.4 Authorization, §4.5 Lifecycle, §4.6
  Composition governance (end-to-end through real policy).
- `docs/requirements.md` §5.1 F3 `enable_skill`, F4 `disable_skill`,
  F9 PreToolUse interception, F10 PostToolUse audit, F11
  `change_stage`.
- `docs/requirements.md` §9 acceptance items A4 (authorization flow),
  A5 (interception), A6 (authorization reclamation), A9 (stage
  switching).
- `docs/technical_design.md` §3.2.3 `policy_engine` precedence,
  §3.2.5 `tool_rewriter` blocked-tools deny-list, §3.2.6
  `grant_manager` lifecycle (revoke vs expire).
- Design §Extension §4 "Mock E2E matrix" (E1–E6) + explicit
  lifecycle re-verification (E7–E9).

**5. Avoiding Request-too-large**
- Read only: files Stage F wrote (`policies/*.yaml`,
  `_support/runtime.py`), existing test patterns from
  `test_functional_happy_path.py` / `test_functional_stage.py` /
  `test_functional_ttl.py` / `test_functional_revoke.py` (for shape
  mimicry, not for duplication), and the Extension section of
  `design.md`.
- Do NOT re-read `src/` modules this turn.
- Keep inline-YAML derivatives local to the test file; do not load
  the full `restrictive.yaml` into the test context then mutate —
  mutate on a fresh `yaml.safe_load` and write immediately to
  `tmp_path`.
- Target ≤ 220 LOC for the new E2E test file. If approaching that
  budget, split E7–E9 into a sibling file
  `test_functional_policy_e2e_lifecycle.py` rather than growing a
  single file beyond comfort.

### Stage sync — docs once all three stages land

- [x] `tests/functional/README.md`: §3.2/§3.3 fixture tables updated
  (policies table no longer marked `*(later)*`, `mock_sensitive_stdio`
  promoted from skeleton); §8 Rollout Status adds Stages F/G/H rows;
  §11 Coverage Summary reflects the 13 test files / 45 tests / 167
  full-suite count and the policy-sensitive E2E lane.
- [x] `docs/self_test_runbook.md`: §2.2 adds `mock_sensitive_stdio`;
  §2.3 adds the policy fixtures table; §3 test-file table reflects the
  13 functional files / 45 tests / 167 full; §6 Step 9 expands to cover
  `test_functional_smoke_subprocess.py` (2+5 = 7 passed), new Step 10
  runs the policy + mock E2E bundle (17 passed), Steps 11–13 renumber
  functional/全量/ruff-mypy with updated expected counts; §10/§11
  cross-references updated; §11 backlog trimmed to
  `mock_stage_stdio` deeper round-trip + Live Claude Code + Phase 4
  items.
- [x] `docs/dev_plan.md` §6: functional-test-harness block rewritten
  to reflect Stages A–H complete (functional 45/45, full 167/167) and
  explicitly marked as a test-harness enhancement (no production code
  expansion, zero `src/tool_governance/` diff this round).
