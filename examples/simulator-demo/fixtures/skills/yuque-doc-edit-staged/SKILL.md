---
skill_id: yuque-doc-edit-staged
name: Yuque Document Editor (Staged)
description: Edit Yuque documents through a staged workflow with read-only analysis, write execution, and terminal verification phases
risk_level: medium
initial_stage: analysis
allowed_tools: []
stages:
  - stage_id: analysis
    description: Read-only document discovery and analysis
    allowed_tools:
      - yuque_search
      - yuque_get_doc
    allowed_next_stages:
      - execution
  - stage_id: execution
    description: Write and edit operations
    allowed_tools:
      - yuque_get_doc
      - yuque_update_doc
    allowed_next_stages:
      - verification
  - stage_id: verification
    description: Read-only verification phase (terminal stage)
    allowed_tools:
      - yuque_get_doc
    allowed_next_stages: []
---

# Yuque Document Editor (Staged)

## Purpose

Demonstrates Stage-first governance with a three-stage workflow: analysis → execution → verification.

This skill enforces stage transitions to separate read-only analysis from write operations, with a terminal verification stage that blocks further transitions.

## Workflow

1. **analysis** (initial stage) — Read-only document discovery and analysis
2. **execution** — Write and edit operations
3. **verification** (terminal stage) — Read-only verification, no further transitions allowed

## Stage Definitions

### Stage: analysis

**Purpose**: Read-only analysis phase. Discover and read documents without making changes.

**Allowed tools**:
- `yuque_search` — Search for documents
- `yuque_get_doc` — Read document content

**Allowed transitions**:
- `execution` — Proceed to write phase after analysis complete

**Guidance**: Do not attempt write operations in this stage. Use this stage to understand document structure and plan changes.

### Stage: execution

**Purpose**: Write and edit phase. Make changes to documents.

**Allowed tools**:
- `yuque_get_doc` — Read document content (for verification before writing)
- `yuque_update_doc` — Update document content

**Allowed transitions**:
- `verification` — Proceed to verification after edits complete

**Guidance**: Make all necessary edits in this stage. Once you transition to verification, you cannot return to execution.

### Stage: verification

**Purpose**: Terminal verification phase. Read-only verification of changes. No further stage transitions allowed.

**Allowed tools**:
- `yuque_get_doc` — Read document content to verify changes

**Allowed transitions**: None (terminal stage)

**Guidance**: This is a terminal stage. Once entered, no further `change_stage` calls will succeed. Use this stage to verify that edits were applied correctly.

## Metadata

```yaml
skill_id: yuque-doc-edit-staged
name: Yuque Document Editor (Staged)
description: Edit Yuque documents through a staged workflow
risk_level: medium
initial_stage: analysis
allowed_tools: []  # Stage-first: tools come from stage.allowed_tools
stages:
  - stage_id: analysis
    description: Read-only analysis phase
    allowed_tools:
      - yuque_search
      - yuque_get_doc
    allowed_next_stages:
      - execution
  - stage_id: execution
    description: Write and edit phase
    allowed_tools:
      - yuque_get_doc
      - yuque_update_doc
    allowed_next_stages:
      - verification
  - stage_id: verification
    description: Terminal verification phase
    allowed_tools:
      - yuque_get_doc
    allowed_next_stages: []  # Terminal stage
```

## Stage-first Governance Behaviors Demonstrated

- **initial_stage**: Skill enters `analysis` stage on `enable_skill`
- **Stage transitions**: Legal transitions follow `allowed_next_stages`, illegal transitions rejected
- **Terminal stage**: `verification` stage has `allowed_next_stages: []`, blocking further transitions
- **Stage-aware tools**: Runtime `active_tools` reflects only current stage's `allowed_tools`
