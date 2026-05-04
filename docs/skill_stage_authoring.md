# Skill Stage Authoring Standard

> Version: 1.0 | Created: 2026-05-03  
> Companion: [Technical Design](./technical_design.md) | [Requirements](./requirements.md)

---

## 1. Core Definitions

### Skill

A **Skill** represents a coherent **business capability**, **operational procedure**, or **workflow** — not merely a grouping of related tools.

- **Purpose**: Encapsulates a complete SOP (Standard Operating Procedure) for accomplishing a specific business goal
- **Content**: The SOP lives in the `SKILL.md` body as Markdown documentation
- **Governance**: Metadata defines authorization boundaries, risk levels, and stage workflow structure

### Stage

A **Stage** represents a **phase within a Skill's workflow** — a distinct step in the SOP with its own tool requirements and risk profile.

- **Purpose**: Enables progressive disclosure of capabilities as the workflow advances
- **Granularity**: Stages correspond to workflow phases (e.g., "diagnosis" → "analysis" → "execution"), not tool categories
- **Tool Governance**: Each stage declares its own `allowed_tools` list

### Tool

A **Tool** is an **external capability** (Read, Write, Bash, MCP tool, etc.) that can be invoked within a stage.

- **Purpose**: Execution mechanism for implementing the SOP
- **Governance**: Tools are the unit of permission control, not the organizing principle for Skills or Stages
- **Relationship**: Tools serve the workflow; the workflow does not exist to group tools

### Metadata vs. SOP

- **SKILL.md body**: Contains the SOP — the "what" and "how" of the workflow
- **SKILL.md frontmatter**: Contains metadata — governance boundaries, stage structure, risk level, tool allowlists

---

## 2. When to Create a Skill

Create separate Skills when they represent **different business capabilities** or **distinct SOPs**. Skills should be split based on:

### Business Goal Boundaries

- **Different user intents**: "Discover knowledge" vs. "Edit documents" vs. "Sync comments"
- **Different outcomes**: "Diagnose performance issues" vs. "Deploy code changes"
- **Different workflows**: "Review pull requests" vs. "Merge pull requests"

### Authorization Boundaries

- **Different risk profiles**: Low-risk read-only exploration vs. high-risk data modification
- **Different approval requirements**: Auto-granted discovery vs. user-confirmed execution
- **Different permission scopes**: Project-level access vs. organization-level access

### SOP Boundaries

- **Different procedures**: Each Skill should have its own coherent SOP
- **Different lifecycles**: Short-lived diagnostic tasks vs. long-running deployment workflows
- **Different stakeholders**: Developer-facing vs. operations-facing capabilities

### Examples

✅ **Good Skill Decomposition** (by business capability):
- `knowledge-discovery` — Search and explore documentation
- `document-editing` — Modify and update documents
- `comment-sync` — Synchronize comments across systems

❌ **Bad Skill Decomposition** (by tool type):
- `yuque-search-skill` — Just wraps search tools
- `yuque-get-doc-skill` — Just wraps read tools
- `yuque-update-doc-skill` — Just wraps write tools

**Why the second approach is wrong**: These are not business capabilities; they're mechanical tool groupings. A user doesn't think "I want to search" — they think "I want to discover knowledge," which may involve searching, reading, and analyzing.

---

## 3. When to Decompose into Stages

Decompose a Skill into Stages when the **same SOP** has distinct phases with different characteristics:

### Tool Requirements Change

- **Progressive disclosure**: Early phases need only read tools; later phases need write/execute tools
- **Risk escalation**: Diagnostic phases are low-risk; remediation phases are high-risk
- **Capability expansion**: Analysis requires limited tools; execution requires broader access

### Workflow Has Sequential Phases

- **Natural progression**: Diagnosis → Analysis → Execution → Verification
- **Decision points**: After analysis, branch to either "execute" or "abort"
- **Iterative refinement**: Execute → Verify → (if failed) → Re-execute

### Risk Profiles Differ

- **Read-only exploration**: Safe, auto-granted, minimal audit
- **Write operations**: Risky, requires reason, detailed audit
- **Destructive actions**: High-risk, requires user confirmation

### Examples

✅ **Good Stage Decomposition** (by workflow phase):

**Skill**: `database-performance-troubleshooting`
- **Stage 1: diagnosis** — Read-only: query logs, check slow queries
- **Stage 2: analysis** — Read + analyze: execution plans, index usage
- **Stage 3: remediation** — Write: create indexes, optimize queries
- **Stage 4: verification** — Read: re-check performance metrics

✅ **Good Stage Decomposition** (with branching):

**Skill**: `document-editing`
- **Stage 1: review** — Read document, check current state
- **Stage 2: edit** — Modify content
- **Stage 3: publish** — Commit changes (terminal)
- **Stage 4: discard** — Abandon changes (terminal)

---

## 4. When NOT to Use Stages

Skills **without stages** are a **fully supported, non-deprecated format**. Use skill-level `allowed_tools` (no stages) when:

### Simple, Uniform Workflows

- **Single-phase operation**: The entire workflow has uniform tool requirements
- **No risk escalation**: All operations have the same risk profile
- **No progressive disclosure needed**: All tools can be exposed upfront

### Low-Risk, Read-Only Skills

- **Pure exploration**: Searching, reading, listing files
- **Diagnostic queries**: Checking status, viewing logs
- **Information retrieval**: Fetching data without modification

### No Stage Transitions Required

- **Linear execution**: No branching, no decision points
- **No retry logic**: No need to loop back to earlier phases
- **No conditional paths**: Single straightforward workflow

### Examples

✅ **Good Non-Staged Skills**:

**Skill**: `list-files`
```yaml
allowed_tools: [Read, Glob]
```
Simple directory exploration — no need for stages.

**Skill**: `search-logs`
```yaml
allowed_tools: [Read, Grep, Bash]
```
Read-only log analysis — uniform tool requirements.

**Skill**: `check-service-status`
```yaml
allowed_tools: [Bash, Read]
```
Single-phase diagnostic — no risk escalation.

---

## 5. Choosing `initial_stage`

The `initial_stage` field specifies the **entry point** of a staged workflow.

### Semantics

- **Optional field**: If omitted, the first stage in the `stages` list is the default entry point
- **Explicit entry**: If declared, `enable_skill` should enter this stage (runtime enforcement is future work)
- **Must be valid**: `initial_stage` must reference a `stage_id` that exists in the `stages` list

### Design Principles

✅ **Prefer the safest entry point**:
- Choose a **read-only** or **discovery** stage as the initial stage
- Avoid defaulting to **execution** or **write** stages
- Start with **low-risk** operations

✅ **Follow natural workflow order**:
- The initial stage should be the logical first step in the SOP
- Users should not need to "back up" from the initial stage

### Examples

✅ **Good `initial_stage` choices**:

```yaml
initial_stage: diagnosis
stages:
  - stage_id: diagnosis      # Read-only, safe entry
    allowed_tools: [Read]
  - stage_id: execution      # Write operations, higher risk
    allowed_tools: [Write, Bash]
```

```yaml
initial_stage: review
stages:
  - stage_id: review         # Safe assessment phase
    allowed_tools: [Read]
  - stage_id: edit           # Modification phase
    allowed_tools: [Edit, Write]
  - stage_id: publish        # Commit phase
    allowed_tools: [Bash]
```

❌ **Bad `initial_stage` choices**:

```yaml
initial_stage: execution     # ❌ Starts with high-risk write operations
stages:
  - stage_id: diagnosis
    allowed_tools: [Read]
  - stage_id: execution
    allowed_tools: [Write, Bash]
```

---

## 6. Designing `allowed_next_stages`

The `allowed_next_stages` field declares **valid successor stages** from the current stage.

### Semantics

- **List of stage_ids**: Each entry must be a valid `stage_id` from the same Skill's `stages` list
- **Empty list = terminal stage**: `allowed_next_stages: []` means no further transitions are permitted
- **Not "allow any"**: An empty list does NOT mean "allow any transition" — it means "no transitions"

### Terminal Stages

A **terminal stage** is one from which no further transitions are allowed:

```yaml
- stage_id: complete
  allowed_tools: [Read]
  allowed_next_stages: []    # Terminal: workflow ends here
```

Terminal stages are appropriate for:
- **Completion states**: Workflow successfully finished
- **Abort states**: Workflow explicitly canceled
- **Error states**: Workflow failed and cannot continue

### Workflow Patterns

✅ **Linear workflow**:

```yaml
stages:
  - stage_id: step1
    allowed_next_stages: [step2]
  - stage_id: step2
    allowed_next_stages: [step3]
  - stage_id: step3
    allowed_next_stages: []    # Terminal
```

✅ **Branching workflow**:

```yaml
stages:
  - stage_id: analysis
    allowed_next_stages: [execute, abort]
  - stage_id: execute
    allowed_next_stages: [verify]
  - stage_id: verify
    allowed_next_stages: []    # Terminal
  - stage_id: abort
    allowed_next_stages: []    # Terminal
```

✅ **Retry / iterative workflow**:

```yaml
stages:
  - stage_id: execute
    allowed_next_stages: [verify, execute]  # Can retry
  - stage_id: verify
    allowed_next_stages: [complete, execute]  # Can loop back
  - stage_id: complete
    allowed_next_stages: []    # Terminal
```

---

## 7. Stage-Level `allowed_tools`

When a Skill defines stages, each stage's `allowed_tools` list is the **tool governance boundary** for that phase.

### Design Principles

✅ **Different stages expose different tools**:
- **Discovery/diagnosis stages**: Read, Glob, Grep
- **Analysis stages**: Read, Bash (for queries)
- **Execution stages**: Write, Edit, Bash (for modifications)
- **Verification stages**: Read (for checking results)

✅ **Minimize tool exposure per stage**:
- Only include tools actually needed for that phase
- Don't carry forward tools from earlier stages unless needed
- Write/execute tools should appear only in execution-type stages

✅ **Tools serve the workflow**:
- Tools are the means, not the end
- Stage boundaries are defined by workflow phases, not by which tools they use
- The same tool (e.g., Bash) may appear in multiple stages for different purposes

### Example

```yaml
stages:
  - stage_id: diagnosis
    description: "Identify slow queries"
    allowed_tools:
      - Read              # Read log files
      - Grep              # Search for patterns
    allowed_next_stages: [analysis, abort]

  - stage_id: analysis
    description: "Analyze query execution plans"
    allowed_tools:
      - Read              # Read query plans
      - Bash              # Run EXPLAIN queries
    allowed_next_stages: [remediation, abort]

  - stage_id: remediation
    description: "Create indexes and optimize"
    allowed_tools:
      - Read              # Verify current schema
      - Write             # Write migration scripts
      - Bash              # Execute migrations
    allowed_next_stages: [verification]

  - stage_id: verification
    description: "Confirm performance improvement"
    allowed_tools:
      - Read              # Re-check metrics
      - Bash              # Run test queries
    allowed_next_stages: []  # Terminal

  - stage_id: abort
    description: "Cancel without changes"
    allowed_tools: []
    allowed_next_stages: []  # Terminal
```

---

## 8. Anti-Patterns

### ❌ Anti-Pattern 1: Splitting by Tool Type

**Wrong**:
```yaml
# Three separate Skills, mechanically split by tool
- skill_id: yuque-read-ops
  allowed_tools: [yuque_get_doc, yuque_list_docs]

- skill_id: yuque-write-ops
  allowed_tools: [yuque_update_doc, yuque_create_doc]

- skill_id: yuque-search-ops
  allowed_tools: [yuque_search]
```

**Why it's wrong**: These are not business capabilities. A user doesn't think "I want to perform read operations" — they think "I want to discover knowledge" or "I want to edit a document."

**Right**:
```yaml
# One Skill per business capability
- skill_id: knowledge-discovery
  stages:
    - stage_id: search
      allowed_tools: [yuque_search, yuque_list_docs]
    - stage_id: read
      allowed_tools: [yuque_get_doc, Read]

- skill_id: document-editing
  stages:
    - stage_id: review
      allowed_tools: [yuque_get_doc, Read]
    - stage_id: edit
      allowed_tools: [yuque_update_doc, Write]
```

### ❌ Anti-Pattern 2: Stages Named by Tool Type

**Wrong**:
```yaml
stages:
  - stage_id: read-stage
    allowed_tools: [Read, Glob]
  - stage_id: write-stage
    allowed_tools: [Write, Edit]
```

**Why it's wrong**: Stage names should reflect **workflow phases**, not tool categories.

**Right**:
```yaml
stages:
  - stage_id: review
    allowed_tools: [Read, Glob]
  - stage_id: modify
    allowed_tools: [Write, Edit]
```

### ❌ Anti-Pattern 3: One Skill Per Tool

**Wrong**: Creating `bash-skill`, `read-skill`, `write-skill`, etc.

**Why it's wrong**: Tools are primitives, not capabilities. Skills should represent what users want to accomplish, not which tools they want to use.

---

## 9. Best Practices

### ✅ Best Practice 1: Split by Workflow Phase

Organize stages around the natural progression of the SOP:

```yaml
stages:
  - stage_id: diagnose      # Identify the problem
  - stage_id: analyze       # Understand root cause
  - stage_id: remediate     # Fix the issue
  - stage_id: verify        # Confirm the fix
```

### ✅ Best Practice 2: Progressive Tool Disclosure

Start with minimal tools and expand as the workflow progresses:

```yaml
stages:
  - stage_id: explore       # Minimal: Read only
    allowed_tools: [Read]
  - stage_id: investigate   # Expanded: Read + query
    allowed_tools: [Read, Bash]
  - stage_id: modify        # Full: Read + write + execute
    allowed_tools: [Read, Write, Bash]
```

### ✅ Best Practice 3: Explicit Terminal States

Always mark completion and abort states as terminal:

```yaml
stages:
  - stage_id: complete
    allowed_next_stages: []  # Explicit terminal
  - stage_id: abort
    allowed_next_stages: []  # Explicit terminal
```

### ✅ Best Practice 4: Meaningful Stage Names

Use names that communicate business intent:

- ✅ `diagnose`, `analyze`, `remediate`, `verify`
- ✅ `review`, `edit`, `publish`, `discard`
- ✅ `discover`, `assess`, `execute`, `confirm`
- ❌ `stage1`, `stage2`, `stage3`
- ❌ `read-phase`, `write-phase`

---

## 10. Examples

### Example 1: Simple Skill Without Stages

**Use case**: List and explore files in a directory

```yaml
---
name: File Explorer
description: "List and read files in the current directory"
risk_level: low
allowed_tools:
  - Read
  - Glob
  - Bash
---

# File Explorer

Simple read-only file exploration. No stages needed — uniform tool requirements.

## Workflow

1. Use Glob to list files
2. Use Read to view file contents
3. Use Bash for basic file operations (ls, find, etc.)
```

### Example 2: Staged Skill with Linear Workflow

**Use case**: Document editing with review → edit → publish flow

```yaml
---
name: Document Editor
description: "Review, edit, and publish documentation"
risk_level: medium
initial_stage: review
stages:
  - stage_id: review
    description: "Read and assess current document"
    allowed_tools:
      - Read
      - yuque_get_doc
    allowed_next_stages: [edit, discard]

  - stage_id: edit
    description: "Modify document content"
    allowed_tools:
      - Read
      - Write
      - yuque_update_doc
    allowed_next_stages: [publish, discard]

  - stage_id: publish
    description: "Commit and publish changes"
    allowed_tools:
      - yuque_update_doc
      - Bash
    allowed_next_stages: []  # Terminal

  - stage_id: discard
    description: "Abandon changes without publishing"
    allowed_tools: []
    allowed_next_stages: []  # Terminal
---

# Document Editor

Staged workflow for safe document editing.

## Workflow

1. **Review**: Read the current document state
2. **Edit**: Make modifications
3. **Publish**: Commit changes, OR
4. **Discard**: Abandon changes
```

### Example 3: Staged Skill with Branching and Retry

**Use case**: Database performance troubleshooting with iterative remediation

```yaml
---
name: Database Performance Troubleshooting
description: "Diagnose and fix database performance issues"
risk_level: high
initial_stage: diagnosis
stages:
  - stage_id: diagnosis
    description: "Identify slow queries and performance bottlenecks"
    allowed_tools:
      - Read
      - Bash
    allowed_next_stages: [analysis, abort]

  - stage_id: analysis
    description: "Analyze query execution plans and index usage"
    allowed_tools:
      - Read
      - Bash
    allowed_next_stages: [remediation, abort]

  - stage_id: remediation
    description: "Create indexes, optimize queries, update schema"
    allowed_tools:
      - Read
      - Write
      - Bash
    allowed_next_stages: [verification, remediation]  # Can retry

  - stage_id: verification
    description: "Verify performance improvements"
    allowed_tools:
      - Read
      - Bash
    allowed_next_stages: [complete, remediation]  # Can loop back if needed

  - stage_id: complete
    description: "Performance issue resolved"
    allowed_tools: []
    allowed_next_stages: []  # Terminal

  - stage_id: abort
    description: "Cancel troubleshooting without changes"
    allowed_tools: []
    allowed_next_stages: []  # Terminal
---

# Database Performance Troubleshooting

Comprehensive workflow for diagnosing and fixing database performance issues.

## Workflow

1. **Diagnosis**: Identify slow queries
2. **Analysis**: Understand root causes
3. **Remediation**: Apply fixes (can retry if needed)
4. **Verification**: Confirm improvements (can loop back to remediation)
5. **Complete**: Issue resolved, OR
6. **Abort**: Cancel without changes
```

---

## 11. Runtime Enforcement (Future Work)

**Note**: The metadata fields defined in this document (`initial_stage`, `allowed_next_stages`, terminal stages) establish the **governance contract** but do not yet enforce runtime behavior.

### Current State (Metadata Only)

- ✅ `initial_stage` can be declared in SKILL.md frontmatter
- ✅ `allowed_next_stages` can be declared per stage
- ✅ `read_skill` exposes complete stage workflow information
- ❌ `enable_skill` does NOT automatically enter `initial_stage`
- ❌ `change_stage` does NOT validate `allowed_next_stages`
- ❌ Terminal stages do NOT block further transitions

### Future Runtime Enforcement

A future change (`enforce-stage-transition-governance`) will implement:

1. **Auto-entry to `initial_stage`**: When `enable_skill` is called, automatically set `current_stage` to `initial_stage`
2. **Transition validation**: `change_stage` will check if the target stage is in `current_stage.allowed_next_stages`
3. **Terminal stage blocking**: Attempting to transition from a terminal stage will be denied
4. **State tracking**: Record `current_stage`, `exited_stages`, `stage_history`, `stage_entered_at`

Until then, the metadata serves as **documentation and design intent** for skill authors.

---

## 12. Summary

### Key Takeaways

1. **Skill = Business Capability**: Not a tool grouping
2. **Stage = Workflow Phase**: Not a tool category
3. **Tool = Execution Means**: Not the organizing principle
4. **Non-staged Skills are valid**: Not deprecated, fully supported
5. **`initial_stage`**: Prefer safe, read-only entry points
6. **`allowed_next_stages: []`**: Means terminal, not "allow any"
7. **Stage-level `allowed_tools`**: Minimize exposure per phase
8. **Split by workflow, not by tools**: Organize around business intent

### Quick Reference

| Concept | Good Example | Bad Example |
|---------|--------------|-------------|
| Skill naming | `knowledge-discovery` | `yuque-read-ops` |
| Stage naming | `diagnose`, `analyze` | `read-stage`, `write-stage` |
| Skill decomposition | By business goal | By tool type |
| Stage decomposition | By workflow phase | By tool category |
| `initial_stage` | `diagnosis` (read-only) | `execution` (write) |
| `allowed_next_stages` | `[verify, abort]` | Omitted when needed |
| Terminal stage | `allowed_next_stages: []` | No explicit terminal |

---

**End of Document**
