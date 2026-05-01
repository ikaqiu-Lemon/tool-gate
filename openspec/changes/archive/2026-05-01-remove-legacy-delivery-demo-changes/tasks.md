# Implementation Tasks

## Stage A: Deletion Impact Report

**Goal**: Identify the complete impact surface of the two legacy demo changes without deleting any files.

**Files to modify**: None (read-only analysis)

**Files to create**: `deletion_impact_report.md` in this change directory

**Verification**: Manual review confirms report covers all five dimensions

- [x] A.1 Read and analyze `openspec/changes/harden-demo-workspace-onboarding/` artifacts (proposal, specs, design, tasks)
- [x] A.2 Read and analyze `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` artifacts
- [x] A.3 Document change status and relationship: creation milestone → hardening → current state
- [x] A.4 List all files touched by each legacy change, grouped by category (specs/, examples/, docs/, scripts/)
- [x] A.5 Classify each file as: "first introduced", "modified", "still active", or "historical only"
- [x] A.6 Trace each requirement in `openspec/specs/delivery-demo-harness/spec.md` to its origin (archived change, active change, or added later)
- [x] A.7 Identify any requirements that exist ONLY in legacy change artifacts and not in main spec
- [x] A.8 Check root `README.md` for references to legacy demo changes
- [x] A.9 Check `examples/README.md` for references to legacy demo changes
- [x] A.10 Check `examples/QUICKSTART.md` for references to legacy demo changes
- [x] A.11 Check workspace READMEs (`examples/01-*/README.md`, `examples/02-*/README.md`, `examples/03-*/README.md`) for references
- [x] A.12 Check if `AGENTS.md` exists and contains demo workspace references
- [x] A.13 Check if `CLAUDE.md` exists and contains demo workspace references
- [x] A.14 Check `docs/` directory for any agent guidance files referencing legacy changes
- [x] A.15 Generate structured deletion impact report with sections: (1) Change status and relationship, (2) Code and documentation change report, (3) Specs impact analysis, (4) Repository entrypoint impact analysis, (5) Deletion execution recommendation
- [x] A.16 Confirm report explicitly states whether deletion is safe to proceed or what must be fixed first

**Completion criteria**: 
- Deletion impact report exists and covers all five dimensions
- Report explicitly lists any requirements that exist only in legacy changes
- Report explicitly lists all entrypoints that reference legacy changes
- Report provides clear go/no-go recommendation

**Rollback**: Delete `deletion_impact_report.md` if regeneration needed

---

## Stage B: Spec and Source-of-Truth Migration

**Goal**: Ensure current source of truth no longer depends on legacy demo changes.

**Files to modify**: `openspec/specs/delivery-demo-harness/spec.md` (apply specs delta from this change)

**Files NOT to modify**: `src/`, `tests/`, `examples/`, legacy change directories

**Verification**: `openspec validate --all` passes

- [x] B.1 Review Stage A report to confirm which requirements need migration
- [x] B.2 Verify that specs delta from this change (`specs/delivery-demo-harness/spec.md`) covers all still-needed requirements from legacy changes
- [x] B.3 If Stage A found requirements only in legacy changes, add them to main spec now (create additional specs delta if needed)
- [x] B.4 Apply specs delta: merge `openspec/changes/remove-legacy-delivery-demo-changes/specs/delivery-demo-harness/spec.md` into `openspec/specs/delivery-demo-harness/spec.md`
- [x] B.5 Run `openspec validate --all` and confirm it passes
- [x] B.6 Verify that `openspec/specs/delivery-demo-harness/spec.md` now contains the 5 ADDED requirements and 1 MODIFIED requirement from this change's specs delta
- [x] B.7 Confirm that main spec explicitly states legacy changes are not canonical guidance
- [x] B.8 Confirm that main spec explicitly states `examples/` and `openspec/specs/delivery-demo-harness/` are canonical demo paths

**Completion criteria**:
- `openspec validate --all` passes
- Main spec contains all still-needed requirements from legacy changes
- Main spec explicitly establishes new canonical source-of-truth boundaries
- No legacy change directories deleted yet

**Rollback**: `git revert` the specs delta commit if validation fails

---

## Stage C: Entrypoint Cleanup

**Goal**: Update repository navigation to point to canonical demo paths instead of legacy changes.

**Files to modify**: Root README, examples README, QUICKSTART, agent guidance (per three-tier strategy)

**Files NOT to modify**: `src/`, `tests/`, demo workspace implementations, legacy change directories

**Verification**: `grep -r "harden-demo-workspace-onboarding\|add-delivery-demo-workspaces" README.md examples/README.md examples/QUICKSTART.md AGENTS.md CLAUDE.md` returns only historical-context mentions with disclaimers

### Tier 1: Primary Entrypoints (must update)

- [x] C.1 Check root `README.md` for demo-related links
- [x] C.2 If root `README.md` links to legacy changes, update to point to `examples/README.md` instead
- [x] C.3 Check root `README_CN.md` (if exists) for demo-related links
- [x] C.4 If root `README_CN.md` links to legacy changes, update to point to `examples/README.md` instead
- [x] C.5 Check `examples/README.md` for references to legacy changes as primary guidance
- [x] C.6 If `examples/README.md` references legacy changes, update to position itself as primary demo entry
- [x] C.7 Check `examples/QUICKSTART.md` for references to legacy changes as primary guidance
- [x] C.8 If `examples/QUICKSTART.md` references legacy changes, update to remove or add "*(historical context only; not canonical)*" disclaimer

### Tier 2: Agent Guidance (update if references exist)

- [x] C.9 Check if `AGENTS.md` exists
- [x] C.10 If `AGENTS.md` exists and mentions demo workspaces, update to point to `examples/` and `openspec/specs/delivery-demo-harness/`
- [x] C.11 Check if `CLAUDE.md` exists
- [x] C.12 If `CLAUDE.md` exists and mentions demo workspaces, update to point to `examples/` and `openspec/specs/delivery-demo-harness/`
- [x] C.13 Check `docs/` directory for other agent guidance files
- [x] C.14 If other agent guidance files reference demo workspaces, update to point to canonical paths

### Tier 3: Workspace READMEs (check but likely no changes)

- [x] C.15 Check `examples/01-knowledge-link/README.md` for references to legacy changes
- [x] C.16 Check `examples/02-doc-edit-staged/README.md` for references to legacy changes
- [x] C.17 Check `examples/03-lifecycle-and-risk/README.md` for references to legacy changes
- [x] C.18 If any workspace README references legacy changes as primary guidance, update with "*(historical context only; not canonical)*" disclaimer (do NOT refactor demo content)

### Verification

- [x] C.19 Run `grep -r "harden-demo-workspace-onboarding\|add-delivery-demo-workspaces" README.md examples/README.md examples/QUICKSTART.md` and confirm only historical-context mentions with disclaimers remain
- [x] C.20 If `AGENTS.md` or `CLAUDE.md` exist, run `grep "harden-demo-workspace-onboarding\|add-delivery-demo-workspaces" AGENTS.md CLAUDE.md` and confirm only historical-context mentions remain
- [x] C.21 Manually verify that root README demo links point to `examples/README.md`
- [x] C.22 Manually verify that `examples/README.md` positions itself as primary demo entry
- [x] C.23 Manually verify that `examples/QUICKSTART.md` does not reference legacy changes as primary guidance

**Completion criteria**:
- All Tier 1 entrypoints updated to point to canonical demo paths
- All Tier 2 entrypoints (if they exist and mention demos) updated to point to canonical paths
- Tier 3 workspace READMEs checked; only updated if they had legacy references
- Verification grep confirms only historical-context mentions remain
- No legacy change directories deleted yet

**Rollback**: `git revert` the entrypoint cleanup commit; or `git checkout HEAD~1 -- <affected-files>` to restore specific files

---

## Stage D: Delete Legacy Changes and Verify

**Goal**: Delete both legacy change directories and verify the repository remains valid.

**Files to delete**: 
- `openspec/changes/harden-demo-workspace-onboarding/` (entire directory)
- `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` (entire directory)

**Files NOT to modify**: `src/`, `tests/`, `examples/`, `openspec/specs/` (except for verification)

**Verification**: Multiple commands (see tasks below)

### Deletion

- [x] D.1 Confirm Stages A, B, and C are complete before proceeding
- [x] D.2 Delete directory `openspec/changes/harden-demo-workspace-onboarding/` using `rm -rf openspec/changes/harden-demo-workspace-onboarding/`
- [x] D.3 Delete directory `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` using `rm -rf openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`

### Verification

- [x] D.4 Run `openspec list` and confirm `harden-demo-workspace-onboarding` does NOT appear in output
- [x] D.5 Run `openspec validate --all` and confirm it passes
- [x] D.6 Run `rg "harden-demo-workspace-onboarding|add-delivery-demo-workspaces" --type md` and confirm only historical-context mentions with disclaimers remain
- [x] D.7 Verify root `README.md` demo links point to `examples/README.md` (not to deleted changes)
- [x] D.8 Verify `examples/README.md` positions itself as primary demo entry (not pointing to deleted changes)
- [x] D.9 Verify `examples/QUICKSTART.md` does not reference deleted changes as primary guidance
- [x] D.10 If `AGENTS.md` exists, verify it points to `examples/` and `openspec/specs/delivery-demo-harness/` (not to deleted changes)
- [x] D.11 If `CLAUDE.md` exists, verify it points to `examples/` and `openspec/specs/delivery-demo-harness/` (not to deleted changes)
- [x] D.12 Verify directory `openspec/changes/harden-demo-workspace-onboarding/` does not exist
- [x] D.13 Verify directory `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` does not exist

### Documentation

- [x] D.14 Create `deletion_verification_report.md` documenting: (1) What was deleted, (2) Verification command results, (3) Any legacy information still preserved and why, (4) Confirmation that all success criteria met
- [x] D.15 Update `docs/dev_plan.md` Addendum to note that these two legacy changes have been removed (add one paragraph stating removal date and referencing this cleanup change)

**Completion criteria**:
- Both legacy change directories deleted
- `openspec list` does not show `harden-demo-workspace-onboarding`
- `openspec validate --all` passes
- Repository navigation points to canonical demo paths
- Deletion verification report documents results
- `docs/dev_plan.md` updated to note removal

**Rollback**: 
- If `openspec validate` fails: `git checkout HEAD~1 -- openspec/changes/harden-demo-workspace-onboarding/ openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` to restore directories; investigate which requirement was orphaned
- If `openspec list` still shows legacy change: Clear OpenSpec cache (check OpenSpec documentation for cache location); re-run `openspec list`
- If navigation broken: `git checkout HEAD~1 -- <affected-files>` to restore entrypoint files; re-run Stage C with additional entrypoints

---

## Scope Guardrails

**In scope for all stages**:
- OpenSpec change artifacts (`openspec/changes/`, `openspec/specs/`)
- Documentation entry points (README, QUICKSTART, agent guidance)
- Deletion impact analysis and verification reports

**Out of scope for all stages**:
- `src/tool_governance/` — no modifications allowed
- `tests/` — no modifications allowed
- `examples/01-*/`, `examples/02-*/`, `examples/03-*/` demo workspace implementations — no modifications to skills, mcp, schemas, contracts, policies
- `hooks/hooks.json` — no modifications
- `.claude-plugin/plugin.json` — no modifications
- `config/default_policy.yaml` — no modifications
- `.mcp.json` (root) — no modifications
- Git history rewrite — no `git reset`, `git rebase`, `git filter-branch`, or similar operations
- Archiving this cleanup change — deferred to user decision after Stage D verification

**If tempted to modify out-of-scope files**: Stop and create a separate follow-up change instead.
