# Design: Safe Removal of Legacy Delivery-Demo Changes

## Context

The repository currently contains two legacy delivery-demo changes that have completed their historical mission but remain in the filesystem:

1. **Active change**: `openspec/changes/harden-demo-workspace-onboarding/` (56/60 tasks, appears in `openspec list`)
2. **Archived change**: `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` (creation milestone, archived 2026-04-21)

These changes collectively established the current `examples/` demo workspace structure and onboarding documentation. However, their continued presence creates confusion:

- **Active change pollution**: `harden-demo-workspace-onboarding` still appears in `openspec list`, suggesting ongoing work when the demo harness is actually complete
- **Source-of-truth ambiguity**: Future readers and AI agents may treat these change artifacts as canonical demo guidance, when the real source of truth is `openspec/specs/delivery-demo-harness/` and the current `examples/` directory
- **Navigation fragmentation**: Documentation may point to legacy change artifacts instead of the canonical demo path

The current state is:
- `openspec/specs/delivery-demo-harness/spec.md` exists and contains 16 requirements (created when `add-delivery-demo-workspaces` was archived)
- `examples/` contains three fully functional demo workspaces with README, QUICKSTART, skills, mcp, schemas, contracts
- `docs/dev_plan.md` has Addendum sections documenting both legacy changes
- Root README and examples README may contain references to legacy changes

**Constraints**:
- Cannot modify `src/tool_governance/` or `tests/` (this is a documentation/specs cleanup only)
- Cannot modify demo workspace implementations (`examples/01-*/`, `examples/02-*/`, `examples/03-*/`)
- Must maintain backward compatibility for users who have already run demos
- Must ensure `openspec validate --all` passes after deletion
- Must not rewrite git history

## Goals / Non-Goals

**Goals:**
1. Remove `harden-demo-workspace-onboarding` from the active change set so `openspec list` no longer shows it
2. Delete both legacy change directories safely without breaking current specs or documentation
3. Establish `examples/` and `openspec/specs/delivery-demo-harness/` as the unambiguous canonical demo source of truth
4. Ensure all still-needed requirements from legacy changes are already in the main spec before deletion
5. Update repository navigation (README, QUICKSTART, agent guidance) to point to canonical demo paths
6. Provide a complete deletion impact report documenting what was removed and why it's safe

**Non-Goals:**
- Modifying demo workspace implementations or adding new demo features
- Refactoring `src/` or `tests/` code
- Rewriting git history or removing legacy changes from commit history
- Archiving this cleanup change itself (deferred until user approval)
- Implementing new OpenSpec features or changing the OpenSpec workflow

## Decisions

### Decision 1: Source-of-Truth Strategy

**Choice**: Establish a two-tier canonical source of truth:
- **Tier 1 (Requirements)**: `openspec/specs/delivery-demo-harness/spec.md` — defines WHAT demo workspaces must do
- **Tier 2 (Implementation)**: `examples/` directory — defines HOW to run demos, with `examples/README.md` and `examples/QUICKSTART.md` as primary entry points

**Rationale**:
- Separates normative requirements (specs) from runnable examples (implementation)
- Aligns with OpenSpec philosophy: specs are long-lived, changes are temporary
- Makes it clear that legacy changes were scaffolding, not the final product

**Alternatives considered**:
- Keep legacy changes as "historical reference" — rejected because it perpetuates source-of-truth ambiguity
- Move all requirements into `docs/requirements.md` — rejected because demo harness is a capability with its own spec, not a core system requirement

### Decision 2: Legacy Change Classification and Deletion Order

**Classification**:
- **Active legacy change** (`harden-demo-workspace-onboarding`): Must be removed from active set to stop appearing in `openspec list`
- **Archived legacy change** (`add-delivery-demo-workspaces`): Already archived, but directory still exists in `archive/`

**Deletion order**: Delete both in the same stage (Stage D) after all prerequisites are met.

**Rationale**:
- Both changes serve the same capability (`delivery-demo-harness`) and should be cleaned up together
- Deleting active change first would leave archived change orphaned with no clear relationship
- Deleting archived change first would leave active change referencing a non-existent predecessor
- Simultaneous deletion after full migration is cleaner and easier to verify

**Alternatives considered**:
- Delete archived change first, then active change — rejected because it creates an intermediate state where active change references deleted artifacts
- Leave archived change indefinitely — rejected because it perpetuates the "where is the source of truth?" problem

### Decision 3: Deletion Impact Analysis Method (Stage A)

**Method**: Generate a structured impact report covering five dimensions:

1. **Change status and relationship**:
   - Document the relationship between the two legacy changes (creation → hardening)
   - Identify which specs they touched and what role each played

2. **Code and documentation change report**:
   - List all files touched by each legacy change, grouped by category (`openspec/specs/`, `examples/`, `docs/`, `scripts/`)
   - Classify each file as: "first introduced by this change", "modified by this change", "still active in current repo", "historical only"

3. **Specs impact analysis**:
   - For each requirement in `openspec/specs/delivery-demo-harness/spec.md`, trace whether it came from archived change, active change, or was added later
   - Identify any requirements that exist ONLY in legacy change artifacts and not in main spec
   - Confirm that deleting legacy changes will not orphan any current requirements

4. **Repository entrypoint impact analysis**:
   - Check root `README.md`, `examples/README.md`, `examples/QUICKSTART.md`, workspace READMEs, `AGENTS.md`, `CLAUDE.md`
   - Identify which entrypoints reference legacy changes as primary guidance
   - Identify which entrypoints would become dangling references after deletion

5. **Deletion execution recommendation**:
   - Recommend whether to proceed with deletion (yes/no)
   - If no, list what must be fixed first
   - If yes, provide recommended deletion sequence and verification commands

**Rationale**:
- Structured report ensures no impact dimension is overlooked
- Traceability from requirements to legacy changes prevents accidental requirement loss
- Entrypoint analysis ensures navigation remains coherent after deletion

**Alternatives considered**:
- Simple file diff — rejected because it doesn't capture semantic relationships (which requirements came from where)
- Manual review only — rejected because it's error-prone and not reproducible

### Decision 4: Repository Entrypoint Cleanup Strategy (Stage C)

**Strategy**: Update all primary navigation documents to point to canonical demo paths, with a three-tier approach:

**Tier 1 — Primary entrypoints** (must be updated):
- Root `README.md` / `README_CN.md`: Change any demo links to point to `examples/README.md`
- `examples/README.md`: Ensure it positions itself as the primary demo entry, not a pointer to legacy changes
- `examples/QUICKSTART.md`: Ensure it does not reference legacy changes as primary guidance

**Tier 2 — Agent guidance** (update if references exist):
- `AGENTS.md`: If it mentions demo workspaces, point to `examples/` and `openspec/specs/delivery-demo-harness/`
- `CLAUDE.md`: Same as above
- Any other agent guidance files in `docs/` or root

**Tier 3 — Workspace READMEs** (check but likely no changes needed):
- `examples/01-knowledge-link/README.md`
- `examples/02-doc-edit-staged/README.md`
- `examples/03-lifecycle-and-risk/README.md`
- These should already be self-contained and not reference legacy changes

**Handling legacy references**:
- If a document must mention legacy changes for historical context, add explicit disclaimer: "*(historical context only; not canonical)*"
- Remove any language suggesting legacy changes are the "current" or "recommended" demo path
- Replace with language directing readers to `examples/QUICKSTART.md` and `openspec/specs/delivery-demo-harness/`

**Rationale**:
- Three-tier approach ensures we don't miss critical entrypoints while avoiding unnecessary churn
- Explicit disclaimers prevent future confusion if historical references remain
- Focusing on navigation (not content) keeps scope minimal

**Alternatives considered**:
- Remove all mentions of legacy changes — rejected because some historical context may be valuable
- Only update root README — rejected because agents may discover `examples/README.md` first and get confused

### Decision 5: Safe Deletion Sequence

**Sequence**:

1. **Stage A: Deletion Impact Report** (read-only analysis)
   - Generate structured impact report covering all five dimensions
   - Output: `deletion_impact_report.md` in change directory
   - Verification: Manual review confirms report is complete
   - **No files modified, no deletions**

2. **Stage B: Spec and Source-of-Truth Migration** (specs delta only)
   - Apply specs delta to `openspec/specs/delivery-demo-harness/spec.md` (already done in this change's specs artifact)
   - Verification: `openspec validate --all` passes
   - **No legacy changes deleted yet**

3. **Stage C: Entrypoint Cleanup** (documentation only)
   - Update root README, examples README, QUICKSTART, agent guidance per Tier 1/2/3 strategy
   - Verification: `grep -r "harden-demo-workspace-onboarding\|add-delivery-demo-workspaces" README.md examples/README.md examples/QUICKSTART.md AGENTS.md CLAUDE.md` returns only historical-context mentions with disclaimers
   - **No legacy changes deleted yet**

4. **Stage D: Delete Legacy Changes and Verify** (destructive)
   - Delete `openspec/changes/harden-demo-workspace-onboarding/`
   - Delete `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`
   - Verification commands:
     - `openspec list` — confirm `harden-demo-workspace-onboarding` not present
     - `openspec validate --all` — confirm passes
     - `rg "harden-demo-workspace-onboarding|add-delivery-demo-workspaces" --type md` — confirm only historical mentions remain
   - Output: `deletion_verification_report.md` documenting what was deleted and verification results

**Why this sequence**:
- **A before B**: Can't safely migrate specs without knowing what's in legacy changes
- **B before C**: Specs must be complete before we redirect navigation away from legacy changes
- **C before D**: Navigation must point to canonical paths before we delete the old paths
- **D last**: Deletion is irreversible (without git history), so it must come after all prerequisites

**Rationale**:
- Each stage has clear entry/exit criteria and verification commands
- Stages A/B/C are non-destructive and easily reversible
- Stage D is destructive but safe because prerequisites ensure nothing breaks

**Alternatives considered**:
- Delete first, then fix navigation — rejected because it creates a broken intermediate state
- Combine B and C into one stage — rejected because specs migration and documentation cleanup are conceptually distinct and should be verified separately

### Decision 6: Rollback Strategy

**Rollback scenarios and responses**:

| Scenario | Detection | Rollback Action |
|----------|-----------|-----------------|
| **Stage A report incomplete** | Manual review finds missing impact dimension | Regenerate report with additional analysis |
| **Stage B: `openspec validate` fails** | Validation error after specs delta | Revert specs delta commit; investigate which requirement was missed |
| **Stage C: Dangling references remain** | `grep` finds unhandled legacy change references | Update missed entrypoints; re-run verification |
| **Stage D: `openspec validate` fails after deletion** | Validation error after directory deletion | `git checkout HEAD~1 -- openspec/changes/harden-demo-workspace-onboarding/ openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`; investigate which requirement was orphaned |
| **Stage D: `openspec list` still shows legacy change** | Legacy change appears in list after deletion | Clear OpenSpec cache; re-run `openspec list`; if persists, investigate OpenSpec state files |
| **Stage D: Navigation broken** | Users report 404s or confusion | `git checkout HEAD~1 -- <affected-files>`; re-run Stage C with additional entrypoints |

**Rollback principles**:
- **Stages A/B/C**: Simple `git revert` of the stage's commit
- **Stage D**: `git checkout` to restore deleted directories from previous commit (does not rewrite history)
- **No git history rewrite**: All rollbacks use forward commits or `git checkout` to restore files
- **Incremental recovery**: Can rollback individual stages without rolling back the entire change

**Rationale**:
- Clear rollback procedures reduce risk of attempting deletion
- Preserving git history means we can always recover deleted content
- Stage-by-stage rollback allows surgical fixes without throwing away all progress

**Alternatives considered**:
- Require full rollback if any stage fails — rejected because it's unnecessarily conservative
- Use git branches for each stage — rejected because it complicates the workflow without adding safety

## Risks / Trade-offs

### Risk 1: Incomplete Requirement Migration
**Risk**: Stage A impact report misses a requirement that exists only in legacy changes, leading to requirement loss after deletion.

**Mitigation**:
- Stage A report explicitly lists every requirement from legacy change specs deltas
- Stage A report cross-references each requirement against `openspec/specs/delivery-demo-harness/spec.md`
- Stage B verification runs `openspec validate --all` before proceeding to Stage C
- If validation fails, rollback is straightforward (revert specs delta commit)

### Risk 2: Navigation Fragmentation
**Risk**: Stage C misses an entrypoint, leaving some documentation pointing to deleted legacy changes.

**Mitigation**:
- Stage C uses a three-tier checklist (primary entrypoints, agent guidance, workspace READMEs)
- Stage D verification includes `rg` search for legacy change names across all markdown files
- If dangling references found, Stage C can be re-run without rolling back Stages A/B
- Rollback is simple: restore affected entrypoint files from previous commit

### Risk 3: OpenSpec Cache Staleness
**Risk**: After deleting `harden-demo-workspace-onboarding/`, `openspec list` still shows it due to cached state.

**Mitigation**:
- Stage D verification explicitly runs `openspec list` and checks output
- If legacy change still appears, clear OpenSpec cache (location TBD based on OpenSpec implementation)
- Document cache-clearing procedure in deletion verification report
- This is a cosmetic issue, not a correctness issue (directory is actually deleted)

### Risk 4: Historical Context Loss
**Risk**: Deleting legacy changes removes valuable historical context about why certain demo design decisions were made.

**Trade-off accepted**:
- Git history preserves all legacy change content (can always `git checkout` old commits)
- Stage A deletion impact report documents the relationship between legacy changes and current state
- `docs/dev_plan.md` Addendum sections remain as historical markers
- This change's artifacts (proposal, specs, design, tasks) document the cleanup rationale
- **Decision**: Historical context is preserved in git history and this change's documentation; filesystem cleanup is worth the trade-off

### Risk 5: Scope Creep Into Demo Workspace Modifications
**Risk**: During Stage C entrypoint cleanup, implementer is tempted to "improve" demo workspace READMEs or fix unrelated issues.

**Mitigation**:
- Design explicitly marks workspace READMEs as Tier 3 (check but likely no changes)
- Tasks will include explicit scope guardrails: "Only modify entrypoint navigation; do not refactor demo content"
- If workspace READMEs need updates, create a separate follow-up change
- This change's success criteria explicitly exclude demo workspace modifications

## Migration Plan

**Deployment**: This is a documentation/specs cleanup change with no runtime deployment. Changes take effect immediately upon commit.

**Rollback strategy**: See Decision 6 above for detailed rollback procedures per stage.

**Verification checklist** (to be executed in Stage D):
- [ ] `openspec list` does not show `harden-demo-workspace-onboarding`
- [ ] `openspec validate --all` passes
- [ ] `rg "harden-demo-workspace-onboarding|add-delivery-demo-workspaces" --type md` returns only historical-context mentions with disclaimers
- [ ] Root `README.md` demo links point to `examples/README.md`
- [ ] `examples/README.md` positions itself as primary demo entry
- [ ] `examples/QUICKSTART.md` does not reference legacy changes as primary guidance
- [ ] `AGENTS.md` and `CLAUDE.md` (if they mention demos) point to `examples/` and `openspec/specs/delivery-demo-harness/`
- [ ] Directory `openspec/changes/harden-demo-workspace-onboarding/` does not exist
- [ ] Directory `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` does not exist

**Success criteria**: All verification checklist items pass.

## Open Questions

1. **OpenSpec cache location**: Where does OpenSpec cache change metadata? (Needed for Risk 3 mitigation)
   - **Resolution approach**: Check OpenSpec source code or documentation; document in tasks
   - **Fallback**: If cache location unknown, document that `openspec list` may show stale data until cache naturally expires

2. **Agent guidance file inventory**: Do `AGENTS.md` or `CLAUDE.md` exist in this repository?
   - **Resolution approach**: Check filesystem in Stage C; if they don't exist, skip Tier 2 updates
   - **Impact**: Low — if files don't exist, no cleanup needed

3. **Workspace README legacy references**: Do any workspace READMEs reference legacy changes?
   - **Resolution approach**: Check in Stage A impact report; if yes, add to Stage C Tier 3 updates
   - **Impact**: Low — workspace READMEs are self-contained and unlikely to reference change artifacts

4. **Archive this cleanup change**: Should this change itself be archived after completion?
   - **Resolution approach**: Deferred to user decision after Stage D verification
   - **Impact**: Low — archiving is a separate operation and doesn't affect cleanup correctness
