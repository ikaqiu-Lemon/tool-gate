# stage-workflow-metadata Specification

## Purpose

Define the metadata schema for Stage-based Skill workflows, including stage definitions, workflow entry points, and stage transition declarations. This specification establishes the metadata contract without implementing runtime enforcement.

## ADDED Requirements

### Requirement: Skill metadata SHALL support stage workflow definitions

Skill metadata SHALL support an optional `stages` field containing a list of stage definitions. Each stage definition MUST include `stage_id`, `description`, `allowed_tools`, and `allowed_next_stages`. Skills without stages remain valid and SHALL continue using skill-level `allowed_tools`.

#### Scenario: Skill with multiple stages

- **WHEN** a SKILL.md frontmatter declares a `stages` field with three stage definitions
- **THEN** the skill indexer parses all three stages and attaches them to `SkillMetadata.stages`

#### Scenario: Skill without stages remains valid

- **WHEN** a SKILL.md frontmatter omits the `stages` field
- **THEN** the skill indexer treats it as a valid skill and uses `SkillMetadata.allowed_tools` for tool governance

#### Scenario: Stage definition includes allowed_next_stages

- **WHEN** a stage definition declares `allowed_next_stages: ["stage-b", "stage-c"]`
- **THEN** the indexer parses this as the list of permitted successor stages for that stage

### Requirement: Skill metadata SHALL support optional initial_stage

Skill metadata SHALL support an optional `initial_stage` field that identifies the entry point stage for the workflow. If `initial_stage` is absent and stages are defined, the first stage in the list SHALL be treated as the default entry point. Runtime enforcement of automatic entry is out of scope for this specification.

#### Scenario: Explicit initial_stage declared

- **WHEN** a SKILL.md frontmatter declares `initial_stage: "diagnosis"`
- **THEN** the skill indexer records "diagnosis" as the workflow entry point in `SkillMetadata.initial_stage`

#### Scenario: No initial_stage with stages defined

- **WHEN** a SKILL.md frontmatter defines stages but omits `initial_stage`
- **THEN** the skill indexer leaves `SkillMetadata.initial_stage` as `None`, indicating the first stage is the default entry point

#### Scenario: initial_stage on skill without stages

- **WHEN** a SKILL.md frontmatter declares `initial_stage` but has no `stages` field
- **THEN** the skill indexer logs a warning and ignores the `initial_stage` field

### Requirement: Terminal stage SHALL be expressed as allowed_next_stages empty list

A stage with `allowed_next_stages: []` SHALL represent a terminal stage, meaning no further stage transitions are permitted from that stage. This is a metadata declaration; runtime enforcement of transition blocking is out of scope for this specification.

#### Scenario: Terminal stage declared

- **WHEN** a stage definition declares `allowed_next_stages: []`
- **THEN** the skill indexer records this stage as a terminal stage in the metadata

#### Scenario: Non-terminal stage with successors

- **WHEN** a stage definition declares `allowed_next_stages: ["review", "abort"]`
- **THEN** the skill indexer records "review" and "abort" as the permitted successor stages

#### Scenario: Stage with no allowed_next_stages field

- **WHEN** a stage definition omits the `allowed_next_stages` field entirely
- **THEN** the skill indexer treats it as having no declared successors (equivalent to terminal stage behavior)

### Requirement: Stage-level allowed_tools SHALL define tool governance boundary

Each stage definition MUST include an `allowed_tools` field that specifies which tools are permitted during that stage. When a skill has stages, stage-level `allowed_tools` SHALL take precedence over skill-level `allowed_tools` for tool governance. Runtime tool surface computation is out of scope for this specification.

#### Scenario: Stage defines specific allowed_tools

- **WHEN** a stage definition declares `allowed_tools: ["Read", "Bash"]`
- **THEN** the skill indexer records these two tools as the governance boundary for that stage

#### Scenario: Different stages have different tool sets

- **WHEN** stage "analysis" declares `allowed_tools: ["Read"]` and stage "execution" declares `allowed_tools: ["Read", "Write", "Bash"]`
- **THEN** the skill indexer records distinct tool sets for each stage

#### Scenario: Stage with empty allowed_tools

- **WHEN** a stage definition declares `allowed_tools: []`
- **THEN** the skill indexer records that no tools are permitted during that stage

### Requirement: Skills without stages SHALL remain a supported format

Skills that omit the `stages` field SHALL be treated as fully valid and supported. Such skills are appropriate for simple, low-risk capabilities that do not require stage-based workflow decomposition. The absence of stages MUST NOT be interpreted as deprecated or legacy format.

#### Scenario: Simple skill without stages

- **WHEN** a SKILL.md frontmatter defines `allowed_tools` but no `stages` field
- **THEN** the skill indexer treats it as a valid skill using skill-level tool governance

#### Scenario: Skill without stages can be enabled

- **WHEN** a skill without stages is enabled via `enable_skill`
- **THEN** the system grants access to the skill's `allowed_tools` without requiring stage selection

#### Scenario: change_stage on skill without stages

- **WHEN** `change_stage` is called on a skill that has no stages defined
- **THEN** the system behavior is undefined in this specification (runtime enforcement SHALL return deny with `error_bucket: skill_has_no_stages` in a future change)
