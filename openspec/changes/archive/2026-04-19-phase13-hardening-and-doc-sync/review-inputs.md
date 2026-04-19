# Review Inputs — phase13-hardening-and-doc-sync

> Hand-off packet for re-running the same review skill against this branch.
> Everything below is the minimum the reviewer needs.

## Change identity

- **Change name**: `phase13-hardening-and-doc-sync`
- **Branch**: `fix/phase13-hardening`
- **Base commit (merge-base with `main`)**: `3cdc5e6` — `feat: bootstrap Tool-Gate Claude Code plugin with runtime governance core`
- **Working tree at closeout**: all Stage A–D edits are **uncommitted** on the
  branch (see "Files touched" below). The reviewer should commit / squash
  according to the project's own policy before re-running the review.

## Scope of this round

Hardening + consistency cleanup + doc sync. **Not Phase 4.**
Core governance chain `index → policy → grant → rewrite → gate` is
unchanged; no new architectural layer was introduced.

## Drift closure status

| ID  | Status  | Notes for the reviewer |
|-----|---------|------------------------|
| D1  | **closed** (fix) | PostToolUse single-stamp; see `hook_handler.py::handle_post_tool_use` |
| D2  | **closed** (fix) | `run_skill_action` deny-by-default when meta is None; `skill.action.deny` audit |
| D3  | **closed** (fix) | `refresh_skills` single scan via `SkillIndexer.current_index()` |
| D4  | **closed** (fix — tests) | `TestMetaNoneEdgeCases` + Stage A/B test classes |
| D5  | **closed** (doc-sync) | `PromptComposer` / `ToolRewriter` constructor signatures in `docs/technical_design.md` §3.2.4, §3.2.5 now match the implementation |
| D6  | **closed** (fix) | `enable_skill_tool` LangChain wrapper now has exact parity with `mcp_server.enable_skill` on `scope` / `granted_by` coercion |
| D7  | **closed** (fix) | New `grant.revoke` audit event emitted by `GrantManager.revoke_grant()`; event boundary vs `skill.disable` and `grant.expire` documented |
| D8  | **closed** (doc-sync) | `state.active_grants` keyed by `skill_id` invariant documented in `docs/technical_design.md` §10-B and stale docstrings in `models/state.py` + `core/state_manager.py` corrected. Re-keying to `grant_id` explicitly deferred. |
| D9  | **pending — backlog** | Not implemented this round. Out of scope per proposal. |
| D10 | **pending — backlog** | Not implemented this round. Out of scope per proposal. |

### One-line answer to the reviewer's likely checklist

- D1 / D2 / D3 / D4 / D6 / D7 — **closed (fix landed + tests)**
- D5 / D8 — **closed (doc sync complete)**
- D9 / D10 — **backlog / Phase 4 pending**, explicitly deferred

## Verification evidence

| Check | Result |
|---|---|
| `python -m pytest -q` | **122 passed**, 0 failed (baseline 104) |
| `claude plugin validate .` (CLI 2.1.111) | **✔ Validation passed** |
| Package smoke import (all core modules + entry points) | OK; `PromptComposer()` instantiates with no args (D5 consistency) |
| `.claude-plugin/plugin.json` parses | OK |
| `hooks/hooks.json` parses and wires `tg-hook` to the four hook events | OK |

## Test-count trajectory

| Stage | Suite size |
|-------|------------|
| Start of Stage A (baseline) | 104 |
| End of Stage A | 109 (+5) |
| End of Stage B | 118 (+9) |
| End of Stage C | 122 (+4) |
| End of Stage D (verification only) | 122 (+0) |

## Files touched on this branch

```
docs/dev_plan.md
docs/technical_design.md
docs/开发计划.md
docs/技术方案文档.md
src/tool_governance/core/grant_manager.py
src/tool_governance/core/skill_indexer.py
src/tool_governance/core/state_manager.py
src/tool_governance/hook_handler.py
src/tool_governance/mcp_server.py
src/tool_governance/models/state.py
src/tool_governance/tools/langchain_tools.py
tests/test_grant_manager.py
tests/test_integration.py
```

Plus the OpenSpec change directory:

```
openspec/changes/phase13-hardening-and-doc-sync/
├── proposal.md
├── specs/tool-governance-hardening/spec.md
├── design.md
├── tasks.md
├── closeout.md
└── review-inputs.md   (this file)
```

Diff stat: **13 files changed, 943 insertions(+), 92 deletions(-)** across the
source + docs tree (OpenSpec artifacts not counted).

## Pointers

- Full drill-down per drift: `openspec/changes/phase13-hardening-and-doc-sync/closeout.md`
- Scope and out-of-scope: `openspec/changes/phase13-hardening-and-doc-sync/proposal.md`
- Normative requirements produced this round:
  `openspec/changes/phase13-hardening-and-doc-sync/specs/tool-governance-hardening/spec.md`
- Minimum-patch design decisions: `openspec/changes/phase13-hardening-and-doc-sync/design.md`
- Implementation task list: `openspec/changes/phase13-hardening-and-doc-sync/tasks.md`

## Request to the reviewer

1. Re-run the same review skill on `fix/phase13-hardening`.
2. Confirm D1 / D2 / D3 / D4 / D5 / D6 / D7 / D8 are all closed.
3. Confirm D9 / D10 are still the only deferred items and that no **new**
   drift appeared.
4. If no new drift: the change is ready to archive.
5. If new drift: file it against a **new** OpenSpec change; do not reopen
   this one.
