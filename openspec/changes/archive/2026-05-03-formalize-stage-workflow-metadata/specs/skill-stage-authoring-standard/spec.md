# skill-stage-authoring-standard Specification

## Purpose

Define authoring standards and guidelines for when and how to decompose Skills into Stages, ensuring Skills represent business capabilities and SOPs rather than mere tool groupings.

## ADDED Requirements

### Requirement: Skills MUST represent business capabilities or SOPs

A Skill MUST represent a coherent business capability, operational procedure, or workflow, not merely a grouping of related tools. The Skill's SOP (SKILL.md body) SHALL describe the workflow, applicable scenarios, and boundaries. Tool lists are governance constraints, not the primary organizing principle.

#### Scenario: Valid skill represents a workflow

- **WHEN** a SKILL.md describes "database performance diagnosis" with steps for identifying slow queries, analyzing execution plans, and recommending indexes
- **THEN** this represents a valid business capability with a clear SOP

#### Scenario: Invalid skill is just a tool group

- **WHEN** a SKILL.md is named "read-tools" and lists `allowed_tools: ["Read", "Bash"]` with no workflow description
- **THEN** this violates the requirement because it groups tools without representing a business capability

#### Scenario: Skill SOP is carried in SKILL.md body

- **WHEN** a SKILL.md contains frontmatter metadata and a Markdown body describing workflow steps
- **THEN** the body text serves as the SOP that guides the model's understanding of the capability

### Requirement: Authoring standard document SHALL define stage decomposition criteria

The system SHALL provide a `docs/skill_stage_authoring.md` document that defines when to decompose a Skill into Stages, when to keep a Skill simple without stages, how to choose `initial_stage`, how to design `allowed_next_stages`, and how to express terminal stages. The document MUST include anti-patterns such as mechanically splitting Skills by tool type.

#### Scenario: Document defines when to use stages

- **WHEN** a skill author reads `docs/skill_stage_authoring.md`
- **THEN** the document explains that stages are appropriate when a workflow has distinct phases with different tool requirements or risk profiles

#### Scenario: Document defines when to avoid stages

- **WHEN** a skill author reads `docs/skill_stage_authoring.md`
- **THEN** the document explains that simple, low-risk capabilities with uniform tool requirements should remain single-stage skills using skill-level `allowed_tools`

#### Scenario: Document explains initial_stage selection

- **WHEN** a skill author reads `docs/skill_stage_authoring.md`
- **THEN** the document explains that `initial_stage` should be the natural entry point of the workflow, typically a read-only analysis or assessment phase

#### Scenario: Document explains allowed_next_stages design

- **WHEN** a skill author reads `docs/skill_stage_authoring.md`
- **THEN** the document explains that `allowed_next_stages` should reflect valid workflow progressions, and that `allowed_next_stages: []` marks a terminal stage

#### Scenario: Document includes anti-patterns

- **WHEN** a skill author reads `docs/skill_stage_authoring.md`
- **THEN** the document includes examples of incorrect decomposition, such as creating separate skills for "read-operations" and "write-operations" instead of workflow-based decomposition

### Requirement: Stage decomposition SHALL follow workflow phases not tool types

When decomposing a Skill into Stages, the decomposition MUST follow natural workflow phases (e.g., "diagnosis", "analysis", "execution", "verification") rather than tool categories (e.g., "read-stage", "write-stage"). Each stage SHALL represent a meaningful step in the business workflow.

#### Scenario: Valid stage decomposition by workflow phase

- **WHEN** a database troubleshooting skill defines stages: "diagnosis" (read-only), "analysis" (read + query tools), "remediation" (write tools)
- **THEN** this represents valid workflow-based decomposition

#### Scenario: Invalid stage decomposition by tool type

- **WHEN** a skill defines stages: "read-stage" (Read, Bash), "write-stage" (Write, Edit)
- **THEN** this violates the requirement because stages are organized by tool type rather than workflow phase

#### Scenario: Stage names reflect business meaning

- **WHEN** stages are named "assess-impact", "prepare-changes", "apply-changes", "verify-results"
- **THEN** the names communicate workflow progression and business intent

### Requirement: initial_stage selection SHALL prioritize safety

When a Skill defines `initial_stage`, the selected stage SHOULD be the safest entry point, typically a read-only or assessment phase. The `initial_stage` MUST be a valid `stage_id` from the skill's `stages` list.

#### Scenario: initial_stage is read-only assessment

- **WHEN** a skill defines stages for "scan", "analyze", "fix" and sets `initial_stage: "scan"`
- **THEN** this follows the safety-first principle by entering at the read-only phase

#### Scenario: initial_stage references valid stage

- **WHEN** a skill declares `initial_stage: "diagnosis"` and includes a stage with `stage_id: "diagnosis"`
- **THEN** the metadata is valid and the indexer accepts it

#### Scenario: initial_stage references invalid stage

- **WHEN** a skill declares `initial_stage: "nonexistent"` but no stage has `stage_id: "nonexistent"`
- **THEN** the skill indexer logs a validation warning

### Requirement: allowed_next_stages SHALL encode valid workflow transitions

Each stage's `allowed_next_stages` list SHALL contain only valid `stage_id` values from the same skill's `stages` list. An empty list (`allowed_next_stages: []`) SHALL indicate a terminal stage. Circular transitions and backward transitions are permitted if they represent valid workflow patterns (e.g., retry loops, iterative refinement).

#### Scenario: allowed_next_stages references valid stages

- **WHEN** stage "analysis" declares `allowed_next_stages: ["execution", "abort"]` and both "execution" and "abort" are defined stages
- **THEN** the metadata is valid

#### Scenario: allowed_next_stages references invalid stage

- **WHEN** stage "analysis" declares `allowed_next_stages: ["nonexistent"]` but no stage has `stage_id: "nonexistent"`
- **THEN** the skill indexer logs a validation warning

#### Scenario: Terminal stage has empty allowed_next_stages

- **WHEN** stage "complete" declares `allowed_next_stages: []`
- **THEN** this indicates no further transitions are permitted from this stage

#### Scenario: Circular transition for retry pattern

- **WHEN** stage "execution" declares `allowed_next_stages: ["verify", "execution"]`
- **THEN** this represents a valid retry pattern where execution can loop back to itself
