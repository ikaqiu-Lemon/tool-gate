# Design — phase13-hardening-and-doc-sync

> Minimum-patch design. **No new architectural layer, no large-scale refactor.**

## 0. Posture

- **No architectural drift from the accepted docs.** The Phase 1–3 core chain
  `index → policy → grant → rewrite → gate` is structurally correct and matches
  `docs/technical_design.md`. There is nothing in this round that requires
  rework of layers, interfaces, or ownership.
- **Phase 1–3 core chain is preserved as-is.** No module boundary is moved, no
  abstraction is introduced, no public signature is changed (D6 is parity work
  *inside* the existing signature; D5 is a doc-only signature correction).
- **This round is strictly Phase 1–3 close-out / hardening.** It closes
  permission-boundary, control-flow, behavioural-parity, audit, and test gaps
  found by the review. Phase 4 backlog is not in scope.

The rest of this document defines the minimum change per drift.

---

## 1. Minimum Fix Designs

### 1.1 D2 — `run_skill_action` deny when metadata missing

**File**: `src/tool_governance/mcp_server.py`, `run_skill_action`.

**Current**: `if meta and op not in meta.allowed_ops: …`. When `meta is None`
the guard short-circuits and the op dispatches unchecked.

**Fix**: replace with an explicit two-branch check.

- If `meta is None` → **deny**: return
  `{"error": f"Skill '{skill_id}' metadata unavailable; operation denied"}`.
  Do **not** dispatch. Do **not** mutate state or grants.
- If `meta is not None` and `op not in meta.allowed_ops` → existing
  `allowed_ops` denial response (unchanged).
- If `meta is not None` and `op` is allowed → dispatch (unchanged).

**Error message**: single stable string prefix so tests/log consumers can match
it (`"metadata unavailable"`). Do **not** invent a new error bucket or error
code — the existing `{"error": …}` shape is reused.

**Audit**: emit one `skill.action.deny` audit record via
`rt.store.append_audit(sid, "skill.action.deny", skill_id=skill_id,
detail={"op": op, "reason": "meta_missing"})`. This reuses the existing audit
channel; no new audit subsystem.

**Non-goals**: no change to `is_grant_valid`, no change to `dispatch`, no new
exception types.

---

### 1.2 D1 — PostToolUse stamps exactly one skill

**File**: `src/tool_governance/hook_handler.py`, `handle_post_tool_use`.

**Current**: nested loop; the inner `break` only exits the stage loop, so the
outer skill loop keeps iterating and a later skill can overwrite
`last_used_at` on the same tool.

**Fix**: introduce an explicit `matched` flag and **early-return from the
matching branch via a single `break` at the skill level**. Minimal rewrite:

```
matched = False
for skill_id, loaded in state.skills_loaded.items():
    meta = state.skills_metadata.get(skill_id)
    if not meta:
        continue
    if tool_name in meta.allowed_tools:
        loaded.last_used_at = datetime.utcnow()
        matched = True
        break
    if meta.stages:
        for stage in meta.stages:
            if tool_name in stage.allowed_tools:
                loaded.last_used_at = datetime.utcnow()
                matched = True
                break
        if matched:
            break
```

Exactly one `(skill, tool)` match wins; once `matched` is set, neither the
stage loop nor the outer skill loop continues. `save()` + `append_audit` calls
below the loop are unchanged.

**Non-goals**: no change to match precedence (top-level before stage-level is
preserved), no change to what happens when no skill matches, no change to the
audit record shape.

---

### 1.3 D6 — `enable_skill_tool` parity with `mcp_server.enable_skill`

**File**: `src/tool_governance/tools/langchain_tools.py`, `enable_skill_tool`.

Two concrete deltas, both small:

1. **`scope` coercion**: mirror `mcp_server.enable_skill` exactly:
   ```
   scope_val: Literal["turn", "session"] = "turn" if scope == "turn" else "session"
   ```
   Pass `scope_val` to `create_grant`. This removes the pydantic-ValidationError
   path that the MCP side does not have.

2. **`granted_by` mapping**: mirror the MCP side:
   ```
   granted_by_val: Literal["auto", "user", "policy"] = (
       "auto" if decision.decision == "auto" else "policy"
   )
   ```
   Pass `granted_by_val` to `create_grant`. Removes the current behaviour of
   feeding `decision.decision` straight in, which is fragile to future
   decision values.

`state.active_grants[skill_id] = grant` stays keyed by `skill_id` on both sides
(see D8 doc note below). Response shape is already identical; no change there.

**Non-goals**: no change to the wrapper's signature, no new validation, no
new audit emission (the LangChain path historically does not emit audit; that
asymmetry is an existing, out-of-scope gap not listed in D1–D10).

---

### 1.4 D3 — `refresh_skills` single effective rescan

**File**: `src/tool_governance/mcp_server.py`, `refresh_skills`.

**Current**: `rt.indexer.refresh()` already rebuilds the index internally, then
the code calls `rt.indexer.build_index()` again and assigns the second result
to `state.skills_metadata`.

**Fix**: drop the redundant call. Use whatever `refresh()` already produced.

```
count = rt.indexer.refresh()
state.skills_metadata = rt.indexer.get_index()   # or equivalent read-only accessor
rt.state_manager.save(state)
return {"refreshed": True, "skill_count": count}
```

If the indexer does not already expose a read-only accessor for the current
index, keep the single `build_index()` call **instead of** `refresh()` (i.e.
pick one, not both). The preferred shape is:

```
state.skills_metadata = rt.indexer.build_index()
count = len(state.skills_metadata)
```

Either variant is acceptable as long as there is exactly **one** directory
scan per call. Response shape (`{"refreshed": True, "skill_count": count}`) is
preserved.

**Non-goals**: no caching layer, no TTL change, no scheduler.

---

### 1.5 D7 — `grant.revoke` audit event boundary vs `skill.disable`

**Files**: `src/tool_governance/core/grant_manager.py` (primary),
`src/tool_governance/mcp_server.py` (`disable_skill`), and
`src/tool_governance/tools/langchain_tools.py` (`disable_skill_tool`).

**Event boundary (normative for this round)**:

- `grant.revoke` — emitted **by `GrantManager`**, once per grant, at the
  moment the grant's status flips to `"revoked"`. Fields: `session_id`,
  `skill_id`, `grant_id`, `reason` ∈ `{"explicit", "ttl", "turn", "session"}`.
  This is the canonical record that a specific grant ceased to be valid.
- `skill.disable` — emitted **by the `disable_skill` entry points**, once per
  user-visible disable operation. Fields as today. Represents the
  user-facing action, not the lifecycle of the underlying grant.

The two events have different semantics and can co-occur for the same
`skill_id` within microseconds on an explicit disable. That is intentional:

- An explicit `disable_skill` call produces **`grant.revoke` (reason="explicit")
  followed by `skill.disable`**.
- A TTL/turn/session sweep that removes a stale grant produces
  **`grant.revoke` only** (no `skill.disable`, because the user did not
  initiate a disable).
  - **Superseded (2026-04-17)**: the final implementation keeps TTL
    expiry on the pre-existing `grant.expire` event and does **not**
    route `cleanup_expired` through `revoke_grant`. `grant.revoke` and
    `grant.expire` are non-overlapping. See
    `docs/technical_design.md` §"Stage B — grant.revoke audit event
    (D7)" and the `test_cleanup_expired_does_not_emit_grant_revoke`
    test for the final boundary.
- Calling `disable_skill` on a skill whose grant was already expired and
  cleaned up produces **`skill.disable` only** (the revoke step is a no-op and
  emits nothing).

**Minimal implementation**:

1. In `GrantManager.revoke_grant(grant_id, reason)`, accept a `reason`
   parameter (default `"explicit"`). Before or immediately after the
   `update_grant_status(grant_id, "revoked")` call, emit
   `store.append_audit(session_id, "grant.revoke", skill_id=…, grant_id=…,
   detail={"reason": reason})`. The `session_id` and `skill_id` are read
   from the grant row being revoked.
2. Callers pass `reason`:
   - `disable_skill` / `disable_skill_tool` → `reason="explicit"`.
   - Lifecycle sweeps in `GrantManager` (TTL/turn/session cleanup) →
     corresponding `reason` value.
3. `disable_skill` continues to emit `skill.disable` as it does today; no
   change there.

**Non-goals**: no new audit transport, no batching, no correlation-id
plumbing beyond `grant_id`.

---

### 1.6 D4 — Minimum test coverage

**File**: `tests/` (new cases added to existing files; no new test module
required).

Minimum coverage this round:

- **D2**: `run_skill_action` with a loaded skill but missing metadata returns
  the deny response; dispatch is not called; one `skill.action.deny` audit is
  written. One positive test (allowed op) and one negative test (disallowed
  op) already exist or must exist — keep them as regression guards.
- **D1**: PostToolUse with two loaded skills where both match the same
  `tool_name` stamps only the first-iterated matching skill; second skill's
  `last_used_at` is unchanged. Include both a top-level match case and a
  stage-level match case.
- **D6**: parametrised test invoking both `mcp_server.enable_skill` and
  `enable_skill_tool` with the same inputs, asserting equivalent grant fields
  (`scope`, `granted_by`, `allowed_ops`) and equivalent response shape. One
  invalid-scope input on both paths asserts equivalent error behaviour.
- **D3**: `refresh_skills()` monkeypatches the indexer scan method and
  asserts it is called exactly once per invocation.
- **D7**: explicit `disable_skill` emits both `grant.revoke` (reason
  `explicit`) and `skill.disable`, in that order; a forced TTL sweep emits
  `grant.revoke` with the TTL reason and no `skill.disable`.

Target: keep total pass count monotonically increasing from the 104+ baseline.
No existing test is deleted; tests are amended only if their assertion
explicitly contradicts the new normative behaviour.

---

## 2. Doc-Sync Design Notes (D5, D8 — no code change this round)

### 2.1 D5 — `PromptComposer` / `ToolRewriter` constructor signatures

Current implementations use a **simpler constructor** than the docs describe
(e.g. fewer positional dependencies, with runtime dependencies injected via
method arguments or a single `runtime` handle). This is functionally
equivalent to the doc'd shape — the same collaborators are reachable, just via
different injection points — but the doc's signatures no longer compile
against the code.

**Doc-sync action**: update `docs/technical_design.md` (+ Chinese mirror
`docs/技术方案文档.md`) so the signature block matches the implementation
verbatim, and add one sentence noting *why* the simpler shape is equivalent
(dependencies are reached through the runtime handle rather than being passed
piecewise at construction). No code change.

### 2.2 D8 — `active_grants` key semantics

`state.active_grants` is keyed by **`skill_id`** on all current write sites
(`mcp_server.enable_skill`, `enable_skill_tool`) and on the read/pop site
(`disable_skill`, `state_manager` cleanup). A docstring in `state_manager.py`
currently claims the dict is keyed by `grant_id`; that claim is the drift.

**Doc-sync action**:

1. In `docs/technical_design.md` (+ Chinese mirror): add a one-paragraph
   "state model" note that `active_grants: dict[skill_id, Grant]` is the
   current invariant and explicitly state the consequence — at most one
   active grant per `(session, skill)` pair.
2. Correct the misleading docstrings in `state_manager.py` to match the
   invariant. (Docstring-only edit; no behaviour change.)

Re-keying to `grant_id` is explicitly deferred; it is **not** a doc-sync item
and is not taken in this round.

---

## 3. Implementation Order

Strictly:

**D2 → D1 → D6 → D3 → D7 → D4 → D5 / D8**

Rationale for the order:

1. **D2** first — it is the only P0 (permission boundary); closing it early
   removes the highest-severity exposure before any other work lands.
2. **D1** next — control-flow correctness in the hot PostToolUse path; small,
   isolated, unblocks D4's PostToolUse tests.
3. **D6** — behavioural parity between entry points; must land before D4's
   parity test can be written meaningfully.
4. **D3** — self-contained perf/correctness fix; independent of D2/D1/D6.
5. **D7** — depends on the `reason` parameter flowing through
   `GrantManager.revoke_grant`; landing it after D6 keeps the two entry-point
   files in a single consistent state when the audit emission is wired.
6. **D4** — tests are written last within the code group so every new branch
   they cover already exists.
7. **D5 / D8** — doc sync runs after code lands so the docs reflect the
   final implemented shape, including whatever minor phrasing choices D2/D7
   settle on (e.g. the exact `reason` discriminator strings).
