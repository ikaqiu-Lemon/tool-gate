---
name: design-drift-review
description: Review whether current code and tests still match OpenSpec change artifacts and local requirements/design docs. Use when checking if implementation drifted from proposal, specs, design, tasks, requirements.md, technical_design.md, or dev_plan.md.
argument-hint: "[change name or paths to docs/code scope]"
disable-model-invocation: true
---

# Design Drift Review

Review the current implementation against approved planning artifacts and report where code is aligned, partially aligned, drifted, undocumented, or missing tests.

## When to use

Use this skill when:
- the project uses OpenSpec and has `openspec/changes/<change-name>/` artifacts;
- you already have `proposal.md`, `design.md`, `tasks.md`, and one or more `specs/**/spec.md` files;
- you also maintain local planning docs such as `docs/requirements.md`, `docs/technical_design.md`, or `docs/dev_plan.md`;
- you want to check whether `src/` and `tests/` still reflect the agreed design.

Do **not** use this skill to write new specs from scratch. Its job is to compare **existing docs** against **existing code/tests**.

## Inputs

$ARGUMENTS

Accept either:
- an OpenSpec change name, e.g. `add-tool-gating-audit`
- explicit doc paths plus code scope, e.g. `openspec/changes/add-tool-gating-audit docs/requirements.md docs/technical_design.md src/ tests/`

If the user does not provide arguments:
1. Look for a single likely active change under `openspec/changes/`.
2. Look for local docs in these common locations:
   - `docs/requirements.md`
   - `docs/technical_design.md`
   - `docs/dev_plan.md`
   - `requirements.md`
   - `technical_design.md`
   - `dev_plan.md`
3. Ask the user to confirm only if multiple plausible change folders or doc sets exist.

## Source priority

Treat the sources in this order:
1. Approved OpenSpec change artifacts for the selected change:
   - `proposal.md`
   - `design.md`
   - `tasks.md`
   - `specs/**/spec.md`
2. Project-level planning docs:
   - requirements doc
   - technical design doc
   - development plan
3. Code and tests:
   - `src/`
   - `tests/`

When sources disagree:
- prefer the selected OpenSpec change artifacts for change-specific intent;
- use project-level docs for broader constraints, architecture, naming, and rollout expectations;
- never assume code is the source of truth when the task is drift review.

## Scope control

Context fills quickly. Never scan the whole codebase blindly.

- Start by listing the exact docs and code folders you will inspect.
- Read docs first, then inspect only the most relevant code paths.
- Default to one feature slice at a time.
- For Python projects, prefer batches such as:
  - one `src/...` module tree plus its matching test files; or
  - at most 5 source files and 5 test files per pass.
- Do not read unrelated entry points, generated files, caches, or build artifacts.
- Skip:
  - `__pycache__/`
  - `.venv/`, `venv/`
  - `*.egg-info/`
  - compiled artifacts
  - coverage outputs
- If the review becomes too large, stop and return a staged review plan instead of continuing to read.

## Review workflow

1. **Identify the baseline artifacts.**
   Determine the selected OpenSpec change and the local requirements/design/plan docs to use.

2. **Extract review checkpoints from docs.**
   Build a compact checklist from the docs:
   - required behaviors
   - non-goals / exclusions
   - architecture and module boundaries
   - data flow and state transitions
   - interfaces / contracts
   - persistence and external dependencies
   - testing expectations and acceptance evidence
   - implementation tasks that should already be reflected in code

3. **Map checkpoints to code and tests.**
   For each checkpoint, inspect the most relevant code path and its nearest tests.

4. **Classify findings.**
   Label each checkpoint as one of:
   - **Aligned** — implementation matches the docs.
   - **Partially aligned** — some intent is implemented, but gaps remain.
   - **Drifted** — implementation contradicts the docs or uses a materially different design.
   - **Undocumented implementation** — behavior exists in code but is not represented in the selected docs.
   - **Missing evidence** — docs require behavior, but the code and/or tests do not show enough evidence.

5. **Check tests separately.**
   Do not treat code presence as enough. Verify whether tests cover the documented behavior, edge cases, and negative paths.

6. **Report with evidence.**
   Cite doc sections and code locations. Be explicit about whether the problem is a missing implementation, a design deviation, a doc drift, or missing tests.

## What to compare

For each relevant feature/module, compare the docs against code on these dimensions:

### 1. Requirement coverage
- Is each required behavior present?
- Are documented constraints, permissions, gates, or policies enforced?
- Are non-goals respected?

### 2. Design conformance
- Do modules, responsibilities, and boundaries match the design doc?
- Is the control flow consistent with the design?
- Are persistence, caching, or external integration points implemented where the design says they should be?

### 3. Task realization
- Do completed implementation tasks appear in code?
- Are there obvious tasks that the codebase still does not reflect?

### 4. Naming and structure drift
- Did major abstractions, file layout, APIs, or state fields drift from the design without the docs being updated?

### 5. Test evidence
- Are there tests for the documented happy path?
- Are edge cases and failure paths covered when the docs imply they matter?
- Do tests assert the documented behavior, or only superficial outcomes?

## Output format

Always structure the final answer like this:

### Review scope
- Selected change:
- Docs reviewed:
- Code reviewed:
- Tests reviewed:
- Items intentionally skipped:

### Executive summary
- 3–7 bullets summarizing the largest alignment wins and the biggest drift risks.

### Findings by checkpoint
For each checkpoint:
- **Checkpoint**
- **Expected from docs**
- **Observed in code/tests**
- **Status**: Aligned / Partially aligned / Drifted / Undocumented implementation / Missing evidence
- **Evidence**: doc path/section + code/test path/function
- **Recommended action**: update code, add tests, or update docs

### Drift register
Create a compact table with columns:
- ID
- Severity (`high` / `medium` / `low`)
- Type (`missing implementation` / `design deviation` / `doc drift` / `missing tests`)
- Affected files
- Suggested next step

### Final judgement
Choose one:
- **No material drift detected**
- **Minor drift detected**
- **Meaningful drift detected**
- **Cannot conclude without narrower scope or missing docs**

## Review rules

- Prefer evidence over speculation.
- Do not rewrite code or docs unless the user explicitly asks.
- Do not silently widen scope.
- If the docs are ambiguous, say so and separate ambiguity from confirmed drift.
- If code intentionally improves the design, mark it as `Undocumented implementation` rather than assuming it is wrong.
- Distinguish between:
  - code missing vs.
  - test missing vs.
  - docs stale.
- When reviewing tests, explain whether assertions match the documented intent or only verify superficial behavior.

## Useful heuristics

When extracting checkpoints, look for:
- headings such as `Requirements`, `Scenarios`, `What Changes`, `Architecture`, `Data Flow`, `Risks`, `Rollout`, `Tasks`
- explicit acceptance criteria
- API contracts and state transitions
- required permissions/policies/tool gating
- rollback/compatibility constraints

## Staged review mode

If the request is broad, do this instead of reading everything:
1. Read only the OpenSpec change docs and project docs.
2. Produce a proposed checkpoint list.
3. Suggest the next review batches, for example:
   - `src/tool_governance/core + matching tests`
   - `src/tool_governance/models + matching tests`
   - `src/tool_governance/storage + matching tests`
4. Wait for the user to choose a batch, or continue one batch at a time if the user explicitly asked for autonomous staged review.

## Example invocations

- `/design-drift-review add-tool-gating-audit`
- `/design-drift-review openspec/changes/add-tool-gating-audit src/tool_governance/core tests/`
- `/design-drift-review openspec/changes/add-tool-gating-audit docs/requirements.md docs/technical_design.md docs/dev_plan.md src/ tests/`

## If the project uses OpenSpec plus local docs

Assume a practical split:
- OpenSpec change folder = change-specific source of truth
- `requirements.md` = broader product/business intent
- `technical_design.md` = architecture and module boundaries
- `dev_plan.md` = execution sequencing and rollout expectations

Use all of them, but do not let a broad project doc override a narrower approved change artifact unless the user tells you to.
