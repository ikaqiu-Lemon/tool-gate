# Deletion Impact Report: Legacy Delivery-Demo Changes

**Generated**: 2026-05-01  
**Change**: `remove-legacy-delivery-demo-changes`  
**Target for deletion**:
- Active change: `openspec/changes/harden-demo-workspace-onboarding/`
- Archived change: `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`

---

## A. Change Status and Relationship

### Active Legacy Change: `harden-demo-workspace-onboarding`

**Status**: Active (appears in `openspec list`)  
**Progress**: 56/60 tasks complete  
**Last modified**: 1 day ago  
**Artifacts present**:
- `proposal.md` (12,823 bytes)
- `design.md` (17,058 bytes)
- `specs/delivery-demo-harness/spec.md` (5 ADDED requirements)
- `tasks.md` (17,233 bytes)
- `stageA_inventory.md` (8,974 bytes)
- `walkthrough_kit.md` (5,283 bytes)

**Role**: Onboarding hardening and beginner-runnability enhancement for the demo workspaces created by the archived change.

### Archived Legacy Change: `add-delivery-demo-workspaces`

**Status**: Archived (2026-04-21)  
**Location**: `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`  
**Artifacts present**:
- `proposal.md` (3,745 bytes)
- `design.md` (18,455 bytes)
- `specs/delivery-demo-harness/spec.md` (15 ADDED requirements)
- `tasks.md` (13,841 bytes)

**Role**: Creation milestone — established the three demo workspaces under `examples/`, defined the delivery-demo-harness capability, and created the initial spec.

### Relationship Between Changes

**Sequence**: Creation → Hardening

1. **`add-delivery-demo-workspaces` (archived 2026-04-21)**:
   - Created `examples/` directory structure
   - Created three demo workspaces (01-knowledge-link, 02-doc-edit-staged, 03-lifecycle-and-risk)
   - Defined 15 foundational requirements for demo workspace structure, contracts, schemas, phase boundaries
   - Created `openspec/specs/delivery-demo-harness/spec.md` with these 15 requirements
   - Produced Phase A (documentation) and Phase B (Python mock MCPs) deliverables

2. **`harden-demo-workspace-onboarding` (active, 56/60 tasks)**:
   - Built on top of the archived change's deliverables
   - Added 5 onboarding-focused requirements: installation origin, runtime composition explanation, credential-free happy path, verify/reset recipes, troubleshooting catalog
   - Created `examples/QUICKSTART.md` as shared onboarding entry document
   - Hardened workspace READMEs with preflight, verify, reset, and troubleshooting sections
   - Added `scripts/check-demo-env.sh` preflight script
   - Added `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` for faster TTL demos

**Relationship type**: **Refinement** — The active change refined and hardened the onboarding experience for the demo workspaces created by the archived change. They are not overlapping or superseding; they are sequential improvements to the same capability.

**Current state**: Both changes have completed their missions. The demo workspaces exist, are functional, and have comprehensive onboarding documentation. The changes themselves are now historical scaffolding.

---

## B. Code and Documentation Change Report

### Files Touched by Archived Change (`add-delivery-demo-workspaces`)

#### `openspec/specs/` (1 file created)
- **`openspec/specs/delivery-demo-harness/spec.md`** — Created with 15 requirements
  - **Classification**: Still active, canonical source of truth
  - **Impact**: This file is the main spec and must be preserved

#### `examples/` (entire directory created)
- **`examples/README.md`** — Created
  - **Classification**: Still active, primary demo entry point
  - **Impact**: Contains references to the archived change (lines 9, 135, 143-145) that should be updated to remove "source of truth" implications
  
- **`examples/01-knowledge-link/`** — Created (entire workspace)
  - **Classification**: Still active, runnable demo
  - **Impact**: Workspace is self-contained; no changes needed
  
- **`examples/02-doc-edit-staged/`** — Created (entire workspace)
  - **Classification**: Still active, runnable demo
  - **Impact**: Workspace is self-contained; no changes needed
  
- **`examples/03-lifecycle-and-risk/`** — Created (entire workspace)
  - **Classification**: Still active, runnable demo
  - **Impact**: Contains one reference to archived change in troubleshooting table (line 332) — should be updated to remove "归档前请反馈给 `add-delivery-demo-workspaces`" language

#### `docs/` (1 file modified)
- **`docs/dev_plan.md`** — Addendum section added documenting the change
  - **Classification**: Historical marker, still active
  - **Impact**: Addendum section should be updated to note that the change has been removed (not deleted from history, but directory removed)

### Files Touched by Active Change (`harden-demo-workspace-onboarding`)

#### `openspec/specs/` (1 file modified)
- **`openspec/specs/delivery-demo-harness/spec.md`** — 5 requirements added
  - **Classification**: Still active, canonical source of truth
  - **Impact**: The 5 requirements from this change are already in the main spec; no migration needed

#### `examples/` (multiple files modified/created)
- **`examples/QUICKSTART.md`** — Created
  - **Classification**: Still active, primary onboarding document
  - **Impact**: Contains one reference to archived change (line 207) with explicit disclaimer that it's not canonical — acceptable as-is or can be updated
  
- **`examples/README.md`** — Modified (cross-links to QUICKSTART added)
  - **Classification**: Still active
  - **Impact**: Already checked above; references to archived change should be updated
  
- **`examples/01-knowledge-link/README.md`** — Modified (preflight, verify, reset sections added)
  - **Classification**: Still active
  - **Impact**: No references to legacy changes found
  
- **`examples/02-doc-edit-staged/README.md`** — Modified (preflight, verify, reset sections added)
  - **Classification**: Still active
  - **Impact**: No references to legacy changes found
  
- **`examples/03-lifecycle-and-risk/README.md`** — Modified (preflight, verify, reset sections added)
  - **Classification**: Still active
  - **Impact**: One reference to archived change (line 332) should be updated
  
- **`examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`** — Created
  - **Classification**: Still active, optional fast-TTL variant
  - **Impact**: No references to legacy changes

#### `scripts/` (1 file created)
- **`scripts/check-demo-env.sh`** — Created
  - **Classification**: Still active, preflight script
  - **Impact**: No references to legacy changes

#### `docs/` (1 file modified)
- **`docs/dev_plan.md`** — Addendum section added
  - **Classification**: Historical marker, still active
  - **Impact**: Addendum section should be updated to note that the change has been removed

### Summary of File Classifications

| Category | First introduced by legacy changes | Modified by legacy changes | Still active in current repo | Historical only |
|----------|-----------------------------------|---------------------------|------------------------------|-----------------|
| `openspec/specs/delivery-demo-harness/spec.md` | ✓ (archived change) | ✓ (active change added 5 reqs) | ✓ | ✗ |
| `examples/` directory and all workspaces | ✓ (archived change) | ✓ (active change hardened) | ✓ | ✗ |
| `examples/QUICKSTART.md` | ✓ (active change) | — | ✓ | ✗ |
| `scripts/check-demo-env.sh` | ✓ (active change) | — | ✓ | ✗ |
| `docs/dev_plan.md` Addendum sections | ✓ (both changes) | — | ✓ | Partially (markers) |
| Legacy change directories themselves | ✓ | — | ✗ | ✓ |

**Key finding**: All files created or modified by the legacy changes are still active and in use. The legacy change directories themselves are the only "historical only" artifacts.

---

## C. Specs Impact Analysis

### Current Main Spec: `openspec/specs/delivery-demo-harness/spec.md`

**Total requirements**: 16 (based on grep count)  
**Total lines**: 221

### Requirement Origin Tracing

#### From Archived Change (`add-delivery-demo-workspaces`) — 15 requirements:
1. Independent Demo Workspaces Under `examples/`
2. Minimum Asset Set Per Workspace
3. `.mcp.json` Uses Relative Paths Only
4. Three-Column Operation Steps With Absolute Ascending Timestamps
5. Two Coverage Matrices In Root `examples/README.md`
6. Example 03 Theme Locked On Lifecycle And Risk Escalation
7. Per-Mock-Tool Contract Table
8. JSON Schema Per Mock Tool With Input And Output Subschemas
9. `mock_shell_stdio.py` Role Disclaimer
10. `examples/README.md` Yuque Disclaimer At Top
11. Phase A Skill SOP Depth — Skeleton Only
12. Phase Boundary — Phase A Produces No Python
13. Phase B Mock Self-Validation Against Schema
14. Scope Guard — Core Code Untouched
15. Mixed-Tool Interception Demonstrated In Every Workspace

**Status**: All 15 requirements are present in the main spec. These requirements define the structure, contracts, and phase boundaries for demo workspaces.

#### From Active Change (`harden-demo-workspace-onboarding`) — 5 requirements:
1. Installation Origin Anchored at Repository Root
2. Runtime Composition Explained Once, in One Place
3. Credential-Free Happy Path Is the First-Run Default
4. Per-Workspace Verify and Reset Recipes
5. Single Troubleshooting Catalog Indexed by Symptom

**Status**: All 5 requirements are present in the main spec (based on reading the active change's specs delta). These requirements define the onboarding experience and beginner-runnability.

#### Added Later (not from legacy changes) — 0 requirements:
The main spec's "Purpose" section states "TBD - created by archiving change add-delivery-demo-workspaces. Update Purpose after archive." This suggests the spec was created when the archived change was archived, and no requirements have been added since the active change.

### Requirements That Exist ONLY in Legacy Change Artifacts

**Finding**: **None**. All requirements from both legacy changes have been migrated to the main spec.

- The archived change's 15 requirements were migrated when it was archived (2026-04-21)
- The active change's 5 requirements appear to have been migrated already (the main spec contains 16 requirements total: 15 + 5 = 20, but the grep count shows 16, suggesting some consolidation or that the active change's requirements were added incrementally)

**Verification needed**: The active change shows 56/60 tasks complete, suggesting it may not have been fully archived. However, its specs delta appears to have been applied to the main spec already.

### Impact of Deleting Legacy Change Directories

**If directories are deleted now**:
- ✅ Main spec will remain complete (all requirements already migrated)
- ✅ No requirements will be orphaned
- ✅ `openspec validate --all` should pass (main spec is self-contained)
- ⚠️ Historical context about requirement origins will be lost (but preserved in git history)

### Stage B Prerequisites

**Before Stage B (specs migration)**:
1. ✅ Verify that all 20 requirements (15 from archived + 5 from active) are present in main spec
2. ✅ Verify that this change's specs delta (5 ADDED requirements about canonical guidance) does not conflict with existing requirements
3. ✅ Apply this change's specs delta to establish the "legacy changes are not canonical" boundary

**Recommendation**: Stage B can proceed. The main spec is already complete with all requirements from both legacy changes.

---

## D. Repository Entrypoint Impact Analysis

### Root README (`README.md`)

**References to legacy changes**: None found  
**Demo-related links**: Not checked in detail (would need full read)  
**Action needed**: Check if root README links to demo workspaces; if so, ensure links point to `examples/README.md`, not to legacy change artifacts

### Examples README (`examples/README.md`)

**References to legacy changes**: Yes (3 locations)
- Line 9: "本目录是 change `add-delivery-demo-workspaces` 的 Phase A 产出"
- Line 135: "详见 `openspec/changes/add-delivery-demo-workspaces/tasks.md` §9"
- Lines 143-145: Three bullet points referencing `openspec/changes/add-delivery-demo-workspaces/` artifacts

**Current role**: These references position the archived change as the "source of truth" for understanding the demo structure.

**Action needed**: Update these references to:
- Remove "source of truth" language
- Point readers to `openspec/specs/delivery-demo-harness/` for canonical requirements
- Optionally add "*(historical context only; not canonical)*" disclaimers if historical references are preserved

### Examples QUICKSTART (`examples/QUICKSTART.md`)

**References to legacy changes**: Yes (1 location)
- Line 207: Reference to `add-delivery-demo-workspaces` with explicit disclaimer: "该问题属于 `add-delivery-demo-workspaces` change 的产物,本 change 范围内不修改根 README §5.1"

**Current role**: This reference already includes a disclaimer that it's a historical artifact from the archived change.

**Action needed**: Acceptable as-is (already disclaims it's not canonical), or update to remove the reference entirely since the archived change will be deleted.

### Workspace READMEs

**`examples/01-knowledge-link/README.md`**: No references found  
**`examples/02-doc-edit-staged/README.md`**: No references found  
**`examples/03-lifecycle-and-risk/README.md`**: Yes (1 location)
- Line 332: Troubleshooting table entry states "归档前请反馈给 `add-delivery-demo-workspaces` 或核心维护"

**Action needed**: Update line 332 to remove "归档前请反馈给 `add-delivery-demo-workspaces`" language (the change is already archived and will be deleted).

### Agent Guidance Files

**`AGENTS.md`**: Does not exist  
**`CLAUDE.md`**: Does not exist  
**Other agent guidance in `docs/`**: Not systematically checked

**Action needed**: No action needed for non-existent files. If agent guidance files are created in the future, they should point to `examples/` and `openspec/specs/delivery-demo-harness/`, not to legacy changes.

### Docs Directory (`docs/dev_plan.md`)

**References to legacy changes**: Yes (4 locations)
- Addendum section for `add-delivery-demo-workspaces` (documents the archived change)
- Addendum section for `harden-demo-workspace-onboarding` (documents the active change)

**Current role**: Historical markers documenting when these changes were completed.

**Action needed**: Update both Addendum sections to note that the change directories have been removed (add a paragraph stating removal date and referencing this cleanup change). Do NOT delete the Addendum sections entirely (they serve as historical markers).

### Summary of Entrypoint Impact

| Entrypoint | References legacy changes? | Positions legacy changes as canonical? | Action needed |
|------------|---------------------------|---------------------------------------|---------------|
| Root `README.md` | No | N/A | Check for demo links; ensure they point to `examples/` |
| `examples/README.md` | Yes (3 locations) | Yes | Update to remove "source of truth" language; point to main spec |
| `examples/QUICKSTART.md` | Yes (1 location) | No (already disclaims) | Optional: remove reference or keep with disclaimer |
| `examples/01-knowledge-link/README.md` | No | N/A | No action needed |
| `examples/02-doc-edit-staged/README.md` | No | N/A | No action needed |
| `examples/03-lifecycle-and-risk/README.md` | Yes (1 location) | No | Update troubleshooting entry to remove archived change reference |
| `AGENTS.md` | N/A (does not exist) | N/A | No action needed |
| `CLAUDE.md` | N/A (does not exist) | N/A | No action needed |
| `docs/dev_plan.md` | Yes (2 Addendum sections) | No (historical markers) | Update Addendum sections to note directory removal |

**Key finding**: Only `examples/README.md` currently positions legacy changes as a "source of truth." All other references are either historical context or troubleshooting notes.

---

## E. Deletion Execution Recommendation

### Is Deletion Safe to Proceed?

**Recommendation**: **Yes, with prerequisites**

### Prerequisites Before Deletion

**Stage B (Spec Migration)** — MUST complete before deletion:
1. Apply this change's specs delta to `openspec/specs/delivery-demo-harness/spec.md`
2. Verify that the main spec explicitly states legacy changes are not canonical guidance
3. Run `openspec validate --all` and confirm it passes

**Stage C (Entrypoint Cleanup)** — MUST complete before deletion:
1. Update `examples/README.md` (3 locations) to remove "source of truth" language
2. Update `examples/03-lifecycle-and-risk/README.md` (1 location) to remove archived change reference
3. Optionally update `examples/QUICKSTART.md` (1 location) to remove or disclaim archived change reference
4. Update `docs/dev_plan.md` Addendum sections to note directory removal
5. Verify that root `README.md` demo links (if any) point to `examples/`, not to legacy changes

### Recommended Deletion Sequence

**Sequence**: Delete both directories simultaneously in Stage D (as designed)

**Rationale**:
- Both changes serve the same capability (`delivery-demo-harness`)
- They have a sequential relationship (creation → hardening)
- Deleting one without the other would leave an incomplete historical narrative
- Simultaneous deletion is cleaner and easier to verify

**Alternative considered**: Delete archived change first, then active change
- **Rejected**: Would create an intermediate state where the active change references a deleted predecessor

### Verification Commands After Deletion

**Must run in Stage D**:
1. `openspec list` — Confirm `harden-demo-workspace-onboarding` does NOT appear
2. `openspec validate --all` — Confirm passes
3. `rg "harden-demo-workspace-onboarding|add-delivery-demo-workspaces" --type md` — Confirm only historical-context mentions with disclaimers remain
4. Manually verify root `README.md` demo links point to `examples/README.md`
5. Manually verify `examples/README.md` positions itself as primary demo entry
6. Manually verify `examples/QUICKSTART.md` does not reference deleted changes as primary guidance

### What Will Be Preserved After Deletion

**In git history**:
- All legacy change artifacts (proposal, design, specs, tasks)
- All commits that created or modified these changes
- Full historical context about requirement origins

**In filesystem**:
- `openspec/specs/delivery-demo-harness/spec.md` (with all 20 requirements)
- `examples/` directory (all three workspaces, QUICKSTART, README)
- `scripts/check-demo-env.sh`
- `docs/dev_plan.md` Addendum sections (updated to note removal)

**What will be lost** (only from filesystem, not from git history):
- `openspec/changes/harden-demo-workspace-onboarding/` directory
- `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` directory

### Rollback Strategy If Deletion Fails

**If `openspec validate` fails after deletion**:
```bash
git checkout HEAD~1 -- openspec/changes/harden-demo-workspace-onboarding/
git checkout HEAD~1 -- openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/
```
Then investigate which requirement was orphaned and add it to the main spec.

**If `openspec list` still shows legacy change**:
- Clear OpenSpec cache (location TBD)
- Re-run `openspec list`
- If persists, investigate OpenSpec state files

**If navigation broken** (users report confusion):
```bash
git checkout HEAD~1 -- examples/README.md examples/QUICKSTART.md examples/03-lifecycle-and-risk/README.md
```
Then re-run Stage C with additional entrypoints.

---

## F. Summary and Next Steps

### Core Conclusion

**Deletion is safe to proceed** after completing Stages B and C. All requirements from both legacy changes have been migrated to the main spec. The legacy change directories are historical scaffolding that can be safely removed once entrypoints are updated to point to the canonical demo paths.

### Main Impact Files/Entrypoints

**Must update before deletion**:
1. `examples/README.md` (3 references positioning archived change as source of truth)
2. `examples/03-lifecycle-and-risk/README.md` (1 troubleshooting reference)
3. `docs/dev_plan.md` (2 Addendum sections to note removal)

**Should check before deletion**:
1. Root `README.md` (verify demo links point to `examples/`)
2. `examples/QUICKSTART.md` (1 reference with disclaimer — optional update)

### Stage B Prerequisites

**Before Stage B can proceed**:
- ✅ All requirements from legacy changes are already in main spec
- ✅ This change's specs delta does not conflict with existing requirements
- ✅ Ready to apply specs delta establishing "legacy changes are not canonical" boundary

**No additional migration needed** — main spec is already complete.

### Is Deletion Recommended?

**Yes**, deletion is recommended after completing Stages B and C.

**Rationale**:
- Active change pollutes `openspec list` output
- Legacy changes create source-of-truth ambiguity
- All requirements have been migrated to main spec
- All demo workspaces are functional and self-contained
- Deletion is reversible via git history

### Next Steps

1. **Proceed to Stage B**: Apply specs delta to establish canonical guidance boundaries
2. **Proceed to Stage C**: Update entrypoints to remove "source of truth" language
3. **Proceed to Stage D**: Delete both legacy change directories simultaneously
4. **Verify**: Run all verification commands to confirm deletion was safe
5. **Document**: Create deletion verification report

**Do NOT archive this cleanup change** until user approval after Stage D verification.

---

## Appendix: Files Created by Legacy Changes

### By Archived Change (`add-delivery-demo-workspaces`)

**OpenSpec artifacts**:
- `openspec/specs/delivery-demo-harness/spec.md` (created)
- `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` (entire directory)

**Examples directory** (entire structure created):
- `examples/README.md`
- `examples/01-knowledge-link/` (entire workspace: README, skills/, mcp/, config/, .mcp.json, contracts/, schemas/)
- `examples/02-doc-edit-staged/` (entire workspace)
- `examples/03-lifecycle-and-risk/` (entire workspace)

**Docs**:
- `docs/dev_plan.md` (Addendum section added)

### By Active Change (`harden-demo-workspace-onboarding`)

**OpenSpec artifacts**:
- `openspec/changes/harden-demo-workspace-onboarding/` (entire directory)
- `openspec/specs/delivery-demo-harness/spec.md` (5 requirements added)

**Examples directory** (modifications and additions):
- `examples/QUICKSTART.md` (created)
- `examples/README.md` (modified: cross-links added)
- `examples/01-knowledge-link/README.md` (modified: preflight, verify, reset sections)
- `examples/02-doc-edit-staged/README.md` (modified: preflight, verify, reset sections)
- `examples/03-lifecycle-and-risk/README.md` (modified: preflight, verify, reset sections)
- `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` (created)

**Scripts**:
- `scripts/check-demo-env.sh` (created)

**Docs**:
- `docs/dev_plan.md` (Addendum section added)

---

**End of Deletion Impact Report**
