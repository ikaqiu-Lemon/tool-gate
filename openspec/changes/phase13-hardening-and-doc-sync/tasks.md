# Tasks — phase13-hardening-and-doc-sync

Four stages. Strict order: **A → B → C → D**. Within Stage A/B, drift order
is **D2 → D1 → D6 → D3 → D7**.

---

## 1. Stage A — Critical correctness fixes (D2, D1)

**In scope**: D2, D1. **Order**: D2 first, then D1.

### 1.1 Files to change
- [ ] 1.1 Edit `src/tool_governance/mcp_server.py` — `run_skill_action` (D2).
- [ ] 1.2 Edit `src/tool_governance/hook_handler.py` — `handle_post_tool_use` (D1).
- [ ] 1.3 No other source files in this stage.

### 1.2 Tests to add or modify
- [ ] 1.4 **D2** Add to `tests/test_integration.py` (or the most appropriate existing file) a case where `skill_id` is in `state.skills_loaded` but `state.skills_metadata[skill_id]` is `None`; assert `run_skill_action` returns the deny response and `dispatch` is **not** called.
- [ ] 1.5 **D2** Add an assertion that a `skill.action.deny` audit record is written with `detail={"op": ..., "reason": "meta_missing"}`.
- [ ] 1.6 **D1** Add/extend a test in `tests/` that loads two skills both claiming `tool_name="X"` (one via top-level `allowed_tools`, one via stage-level), fires PostToolUse, and asserts only the **first-iterated** matching skill has `last_used_at` stamped; the other's `last_used_at` is unchanged.
- [ ] 1.7 **D1** Keep existing PostToolUse tests green.

### 1.3 Commands to run after the stage
- [ ] 1.8 `pytest -q` — full suite passes, count ≥ 104 + new cases.
- [ ] 1.9 `pytest -q tests/test_integration.py` — integration subset green.
- [ ] 1.10 `python -c "import json,sys; json.load(open('.claude-plugin/plugin.json'))"` — plugin manifest still parses.

### 1.4 Docs to sync after the stage
- [ ] 1.11 `docs/dev_plan.md` (+ mirror `docs/开发计划.md`) — mark D2 and D1 as closed under the Phase 1–3 close-out section; one line each.
- [ ] 1.12 `docs/technical_design.md` (+ mirror `docs/技术方案文档.md`) — update the `run_skill_action` contract paragraph to state deny-by-default when meta is `None`; update the PostToolUse paragraph to state the single-stamp rule.
- [ ] 1.13 `docs/requirements.md` (+ mirror `docs/需求文档.md`) — **no change expected**; only touch if a new requirement-level clarification surfaced. If touched, record exactly what and why in the commit message.

### 1.5 Explicitly forbidden in this stage
- [ ] 1.14 Do **not** introduce a new error-code taxonomy or new audit event type beyond `skill.action.deny`.
- [ ] 1.15 Do **not** refactor `run_skill_action` beyond the deny branch.
- [ ] 1.16 Do **not** rewrite the PostToolUse loop into a helper function; the `matched` flag + `break` is the intended minimal shape.
- [ ] 1.17 Do **not** change the audit record shape of `tool.call` or any existing event.
- [ ] 1.18 Do **not** start D6 / D3 / D7 work in this stage.

---

## 2. Stage B — Consistency and audit cleanup (D6, D3, D7)

**In scope**: D6, D3, D7. **Order**: D6 → D3 → D7.

### 2.1 Files to change
- [ ] 2.1 Edit `src/tool_governance/tools/langchain_tools.py` — `enable_skill_tool`: mirror `scope` coercion and `granted_by` mapping from `mcp_server.enable_skill` (D6).
- [ ] 2.2 Edit `src/tool_governance/mcp_server.py` — `refresh_skills`: drop the redundant second scan (D3).
- [ ] 2.3 Edit `src/tool_governance/core/grant_manager.py` — `revoke_grant` accepts a `reason` parameter (default `"explicit"`) and emits a `grant.revoke` audit record with `session_id`, `skill_id`, `grant_id`, `detail={"reason": reason}` (D7).
- [ ] 2.4 Update callers of `revoke_grant`:
  - `src/tool_governance/mcp_server.py::disable_skill` → pass `reason="explicit"`.
  - `src/tool_governance/tools/langchain_tools.py::disable_skill_tool` → pass `reason="explicit"`.
  - Any lifecycle sweep inside `GrantManager` (TTL/turn/session) → pass the corresponding reason (`"ttl"`, `"turn"`, `"session"`).
- [ ] 2.5 No other source files in this stage.

### 2.2 Tests to add or modify
- [ ] 2.6 **D6** Add a parametrised test that invokes both `mcp_server.enable_skill` and `enable_skill_tool` with the same inputs and asserts:
  - Same `Grant.scope`, `Grant.allowed_ops`, and `Grant.granted_by`.
  - Same response shape and `granted` value.
  - Same key used in `state.active_grants` (both keyed by `skill_id`).
- [ ] 2.7 **D6** Add a test where `scope="invalid"` is passed to both entry points; assert both coerce to `"session"` (no `ValidationError` raised from the LangChain side).
- [ ] 2.8 **D3** Add a test that monkeypatches the indexer's scan function (`build_index` or equivalent) and asserts a single `refresh_skills()` call triggers exactly one scan.
- [ ] 2.9 **D7** Add a test that explicit `disable_skill` emits a `grant.revoke` audit record with `detail.reason == "explicit"` **followed by** a `skill.disable` record; order is asserted.
- [ ] 2.10 **D7** Add a test that a forced lifecycle sweep (e.g. expired TTL cleanup) emits `grant.revoke` with the expected `reason` and **no** `skill.disable`.
- [ ] 2.11 **D7** Add a test that `disable_skill` on a skill whose grant was already cleaned up emits `skill.disable` only (no `grant.revoke`).

### 2.3 Commands to run after the stage
- [ ] 2.12 `pytest -q` — full suite green.
- [ ] 2.13 `pytest -q tests/test_grant_manager.py tests/test_integration.py` — focused re-run on the touched areas.
- [ ] 2.14 `python -c "import json,sys; json.load(open('.claude-plugin/plugin.json'))"` — manifest still parses.

### 2.4 Docs to sync after the stage
- [ ] 2.15 `docs/technical_design.md` (+ mirror) — update:
  - `enable_skill` contract: state that the LangChain wrapper and MCP entry point apply identical `scope` coercion and `granted_by` mapping.
  - `refresh_skills` contract: state single effective rescan per call.
  - Audit events section: add `grant.revoke` with its fields and the `reason` discriminator; clarify the event boundary vs `skill.disable`.
- [ ] 2.16 `docs/dev_plan.md` (+ mirror) — mark D6 / D3 / D7 as closed under Phase 1–3 close-out.
- [ ] 2.17 `docs/requirements.md` (+ mirror) — no change expected; touch only if a requirement-level clarification is surfaced.

### 2.5 Explicitly forbidden in this stage
- [ ] 2.18 Do **not** introduce a new audit transport, batching, or correlation-id scheme.
- [ ] 2.19 Do **not** re-key `state.active_grants` by `grant_id` (that is D8, and D8 is doc-sync only this round).
- [ ] 2.20 Do **not** change the public signature of `enable_skill` / `enable_skill_tool` / `disable_skill` / `disable_skill_tool`.
- [ ] 2.21 Do **not** add caching, TTL, or scheduling to `refresh_skills`.
- [ ] 2.22 Do **not** emit audit from the LangChain path for enable/disable unless strictly required by D7's `grant.revoke` contract (the LangChain enable path remains audit-silent in this round).
- [ ] 2.23 Do **not** start D4 / D5 / D8 work in this stage.

---

## 3. Stage C — Tests and doc sync (D4, D5, D8)

**In scope**: D4 coverage audit + gap-fill; D5 and D8 are doc-only.

### 3.1 Files to change
- [ ] 3.1 Test files under `tests/` — see 3.2. **No source edits** beyond docstring fixes listed below.
- [ ] 3.2 `src/tool_governance/core/state_manager.py` — correct the docstring that currently describes `active_grants` as keyed by `grant_id` (D8; docstring-only).
- [ ] 3.3 `docs/technical_design.md` (+ mirror `docs/技术方案文档.md`) — D5 + D8 sync edits described in 3.4.

### 3.2 Tests to add or modify
- [ ] 3.4 **D4** Audit the test suite for the minimum coverage listed in `specs/tool-governance-hardening/spec.md` §"Test coverage MUST exist for hardening branches" and `design.md` §1.6. Any missing case added here.
- [ ] 3.5 **D4** Add a session-scoped regression test that asserts the total pass count is **greater** than the pre-change baseline recorded at Stage A start (soft assertion — capture the count in `tests/` via `conftest` if convenient, otherwise enforce via CI/README note).
- [ ] 3.6 **D5 / D8** No new tests required; these are doc-only.

### 3.3 Commands to run after the stage
- [ ] 3.7 `pytest -q` — full suite green, count strictly greater than Stage A baseline.
- [ ] 3.8 `pytest -q --collect-only | tail -5` — confirm new cases are discovered.
- [ ] 3.9 `grep -n "grant_id" src/tool_governance/core/state_manager.py` — spot-check the D8 docstring fix landed.

### 3.4 Docs to sync after the stage
- [ ] 3.10 **D5** `docs/technical_design.md` (+ mirror `docs/技术方案文档.md`) — replace the drifted `PromptComposer` / `ToolRewriter` constructor signatures with the current implementation signatures verbatim, and add one sentence stating the simpler shape is functionally equivalent because dependencies are reached via the `runtime` handle rather than passed piecewise at construction.
- [ ] 3.11 **D8** `docs/technical_design.md` (+ mirror `docs/技术方案文档.md`) — add a short "state model" note: `active_grants: dict[skill_id, Grant]` is the current invariant; at most one active grant per `(session_id, skill_id)`; re-keying to `grant_id` is explicitly deferred.
- [ ] 3.12 `docs/dev_plan.md` (+ mirror `docs/开发计划.md`) — append D8, D9, D10 to the deferred-backlog section with a one-line rationale each (D8: pending re-keying migration; D9/D10: Phase 4 backlog).
- [ ] 3.13 `docs/requirements.md` (+ mirror `docs/需求文档.md`) — no change.

### 3.5 Explicitly forbidden in this stage
- [ ] 3.14 Do **not** re-key `active_grants` in code.
- [ ] 3.15 Do **not** change `PromptComposer` / `ToolRewriter` signatures to match the docs — the direction is docs → code reality, not the other way round.
- [ ] 3.16 Do **not** introduce a new top-level doc file; sync into the existing canonical set only.
- [ ] 3.17 Do **not** reconcile the English/Chinese doc version-stamp drift (v1.1 vs v1.2); it is a noted-but-unfixed item per the proposal.
- [ ] 3.18 Do **not** start Stage D closeout work until every Stage C box is ticked.

---

## 4. Stage D — Re-review preparation and closeout

**In scope**: regression, plugin validation, fix summary, inputs for a re-run
of the same review skill. **Out of scope**: any Phase 4 implementation.

### 4.1 Files to change
- [ ] 4.1 Create `openspec/changes/phase13-hardening-and-doc-sync/closeout.md` with:
  - A short summary of what each of D1–D4, D6, D7 changed in code (1–2 lines each).
  - What D5 and D8 changed in docs (1–2 lines each).
  - What D9 and D10 remain deferred (1 line each, pointing to backlog).
  - The final Drift Resolution Matrix status (copied from `specs/.../spec.md`, updated with "resolved / doc-synced / deferred" column populated).
- [ ] 4.2 Create `openspec/changes/phase13-hardening-and-doc-sync/review-inputs.md` — a minimal hand-off packet for re-running the same review skill:
  - Branch name, final commit SHA (fill in at the moment of closeout).
  - Files touched (generated from `git diff --name-only <merge-base> HEAD`).
  - Test counts: pre-baseline, post-Stage-A, post-Stage-B, post-Stage-C.
  - Explicit statement: "Phase 4 backlog not implemented in this round; D9/D10 deferred."
  - Pointer to `closeout.md`.
- [ ] 4.3 No source file edits in this stage.

### 4.2 Tests to add or modify
- [ ] 4.4 No new tests. Regression only.

### 4.3 Commands to run after the stage
- [ ] 4.5 `pytest -q` — full regression, all green.
- [ ] 4.6 `pytest -q --tb=short` — confirm no warning regressions introduced across stages.
- [ ] 4.7 `python -c "import json; json.load(open('.claude-plugin/plugin.json'))"` — plugin manifest valid.
- [ ] 4.8 If a CLI validator exists: `openspec validate phase13-hardening-and-doc-sync` (or equivalent). Skip gracefully if not available, but record in `closeout.md` that it was checked.
- [ ] 4.9 `git status --porcelain` — confirm working tree matches intent (no stray files, no accidentally staged changes).
- [ ] 4.10 `git diff --stat $(git merge-base HEAD main)..HEAD` — paste into `review-inputs.md` §"Files touched".

### 4.4 Docs to sync after the stage
- [ ] 4.11 `docs/dev_plan.md` (+ mirror `docs/开发计划.md`) — add a dated close-out entry for this change: "phase13-hardening-and-doc-sync closed on <date>; D1–D4, D6, D7 fixed; D5, D8 doc-synced; D9, D10 deferred; Phase 4 not started".
- [ ] 4.12 `docs/technical_design.md` (+ mirror) — final consistency pass: re-read the sections touched across Stages A–C and confirm no lingering contradictions between paragraphs. Only edit if a contradiction is found.
- [ ] 4.13 `docs/requirements.md` (+ mirror) — no change expected.

### 4.5 Explicitly forbidden in this stage
- [ ] 4.14 Do **not** implement any Phase 4 item (Langfuse, funnel metrics, extra error buckets, CHANGELOG, benchmarks).
- [ ] 4.15 Do **not** start a new change directory.
- [ ] 4.16 Do **not** rewrite docs beyond the scoped edits; this stage is consistency-pass + summary, not editorial.
- [ ] 4.17 Do **not** force-push, rebase, or squash without explicit user instruction.
- [ ] 4.18 Do **not** archive the change before the user has re-run the review skill and confirmed drift is resolved.
