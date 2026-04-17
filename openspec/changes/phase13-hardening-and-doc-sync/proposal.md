# Proposal — phase13-hardening-and-doc-sync

> Scope: post Phase 1–3 review hardening + doc sync. **Not** Phase 4.
> Review verdict baseline: **Minor drift detected**, 104+ tests passing, end-to-end
> `index → policy → grant → rewrite → gate` strongly consistent.

## Why

A focused review of the Phase 1–3 implementation against the canonical docs surfaced
ten drift points (D1–D10). The core runtime path is sound, but a small set of
**permission boundary, audit, and behavioural-consistency** gaps need to be closed
before any further capability work, and the canonical docs need to be re-synced so
that future changes start from an accurate spec baseline. This change exists to
discharge exactly that backlog — nothing more.

## What Changes

This change is organised into **three explicit groups**. Only the first two are
implemented in this round.

### Group A — Fix now (P0/P1, in priority order)

Implementation order is fixed: **D2 → D1 → D6 → D3 → D7 → D4**.

- **D2** `run_skill_action` permission boundary: when `meta is None`, the
  `allowed_ops` check is currently skipped, allowing any `op` through. Treat a
  missing meta as deny-by-default and return a structured error.
- **D1** `handle_post_tool_use` nested-loop control flow: the inner `break` does
  not exit the outer skill loop, so a later skill can overwrite `last_used_at` on
  the same tool. Stamp the first matching skill only and exit cleanly.
- **D6** `enable_skill` behavioural parity between
  `tools/langchain_tools.py` and `mcp_server.py`: align argument coercion,
  Pydantic validation, error shape, and `active_grants` write semantics so both
  entry points are observably equivalent.
- **D3** `refresh_skills` double scan: the index is scanned twice per call.
  Reduce to a single scan and return the same response shape.
- **D7** Missing `grant.revoke` audit event: emit a structured audit record on
  every grant revocation path (explicit revoke, TTL/turn/session expiry sweep).
- **D4** Test gap for the `meta is None` branch in `run_skill_action` and any
  related deny-by-default paths introduced by D2.

### Group B — Doc sync (no runtime behaviour change)

- **D5** `PromptComposer` / `ToolRewriter` constructor signatures in
  `docs/technical_design.md` have drifted from the implementation. Update the
  design doc to match the current signatures; no code change.
- **D8** `state.active_grants.pop(skill_id, ...)` key semantics: the dict is
  keyed by **grant_id** in some paths and treated as keyed by **skill_id** in
  others. This round only **documents** the current invariant in the design doc
  and adds a `.. note::` in the relevant docstrings; no key migration.

### Group C — Backlog only (explicitly out of scope this round)

- **D9**, **D10** — deferred to their respective planned phases. Recorded here
  only so the proposal is exhaustive over D1–D10.

## Capabilities

This change does **not** introduce or modify any spec-level capability.
All edits are bug fixes, audit-event emission, behavioural alignment, and
documentation sync against already-accepted requirements.

### New Capabilities
- _(none)_

### Modified Capabilities
- _(none — no requirement-level behaviour changes; existing requirements are
  being correctly enforced where they currently are not)_

## Out of Scope (this round)

Explicitly **not** in this change, even if adjacent:

- Phase 4 work of any kind
- Langfuse integration
- Funnel metrics
- Additional error buckets beyond what D2/D7 strictly require
- CHANGELOG generation
- Benchmarks
- D9, D10
- Any refactor of `active_grants` keying (D8 is doc-only this round)
- Any change to the canonical doc set beyond the sync targets listed below
- Renaming, splitting, or merging existing docs

## Canonical Docs & Sync Targets

Canonical files (reuse, do **not** create new ones):

| Doc          | Canonical (English)        | Mirror (Chinese)        |
|--------------|----------------------------|-------------------------|
| Requirements | `docs/requirements.md`     | `docs/需求文档.md`       |
| Tech design  | `docs/technical_design.md` | `docs/技术方案文档.md`    |
| Dev plan     | `docs/dev_plan.md`         | `docs/开发计划.md`       |

> **Noted drift (not fixed in this change):** the Chinese mirrors are at a later
> version stamp (v1.2 / 2026-04-16) than the English canonicals (v1.1 /
> 2026-04-15). Per project policy English files are canonical. Both sets are
> updated together in the sync steps below; reconciliation of the version-stamp
> drift itself is **out of scope**.

### Per-phase doc-sync obligations

End of **Group A (fix now)**:
- `docs/dev_plan.md` + `docs/开发计划.md` — record D1/D2/D3/D6/D7 as closed
  hardening items under the Phase 1–3 retrospective; note new test coverage
  added by D4.
- `docs/technical_design.md` + `docs/技术方案文档.md` — update the
  `run_skill_action` deny-by-default rule, the PostToolUse single-stamp rule,
  the `enable_skill` parity contract, and the `grant.revoke` audit event in the
  relevant sections only.
- `docs/requirements.md` + `docs/需求文档.md` — no change expected; touch only
  if a fix surfaces a requirement-level clarification.

End of **Group B (doc sync)**:
- `docs/technical_design.md` + `docs/技术方案文档.md` — D5 signature
  corrections for `PromptComposer` / `ToolRewriter`; D8 `active_grants` key
  semantics noted as a known invariant pending future migration.
- `docs/dev_plan.md` + `docs/开发计划.md` — append D8/D9/D10 to the deferred
  backlog section with a one-line rationale each.

## Impact

- **Code**: `src/tool_governance/mcp_server.py`,
  `src/tool_governance/hook_handler.py`,
  `src/tool_governance/tools/langchain_tools.py`,
  `src/tool_governance/core/grant_manager.py` (audit emission only),
  `src/tool_governance/core/skill_indexer.py` (refresh path only).
- **Tests**: `tests/test_integration.py` and a new/expanded test for the
  `meta is None` branch; existing 104+ tests must continue to pass.
- **Docs**: the six files listed above, scoped strictly to the sync table.
- **APIs / external behaviour**: no breaking changes. `run_skill_action` gains
  a deny response for a previously-undefined branch; `enable_skill` returns
  consistently across MCP and LangChain entry points; one new structured audit
  event (`grant.revoke`) is emitted.
- **Dependencies**: none added or removed.
