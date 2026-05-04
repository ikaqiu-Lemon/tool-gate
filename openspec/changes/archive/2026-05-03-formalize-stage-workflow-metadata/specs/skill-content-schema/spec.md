# skill-content-schema Specification

## Purpose

Define the content schema returned by `read_skill` and `SkillContent`, ensuring stage workflow information is exposed to the model when stages are defined.

## MODIFIED Requirements

### Requirement: Read skill complete SOP

The `read_skill` MCP tool SHALL accept a `skill_id` parameter and return the skill's complete content including: metadata (all SkillMetadata fields including `initial_stage` and stage definitions with `allowed_next_stages`), SOP text (Markdown body), and usage examples. When stages are defined, the response MUST expose the complete stage workflow information. The result MUST be served from cache on subsequent calls within the same session.

#### Scenario: Read an existing skill

- **WHEN** the model calls `read_skill("repo-read")`
- **THEN** the system returns the full SOP content including metadata, workflow steps, allowed_tools list, and risk information

#### Scenario: Read a nonexistent skill

- **WHEN** the model calls `read_skill("nonexistent-skill")`
- **THEN** the system returns an error response indicating the skill was not found

#### Scenario: Cache hit on repeated read

- **WHEN** the model calls `read_skill("repo-read")` twice within the TTL window (default 300s)
- **THEN** the second call returns the same result from cache without re-reading the SKILL.md file from disk

#### Scenario: Read skill with stage workflow

- **WHEN** the model calls `read_skill` on a skill that defines stages with `initial_stage` and `allowed_next_stages`
- **THEN** the system returns `SkillContent` including all stage definitions, the `initial_stage` value, and each stage's `allowed_next_stages` list

#### Scenario: Read skill without stages

- **WHEN** the model calls `read_skill` on a skill that has no stages defined
- **THEN** the system returns `SkillContent` with skill-level `allowed_tools` and no stage information

## ADDED Requirements

### Requirement: SkillContent SHALL expose stage workflow information

When a skill defines stages, `SkillContent` MUST include the complete stage workflow structure: `initial_stage` (if declared), and for each stage its `stage_id`, `description`, `allowed_tools`, and `allowed_next_stages`. This enables the model to understand the workflow structure and stage transition constraints.

#### Scenario: SkillContent includes initial_stage

- **WHEN** `read_skill` is called on a skill with `initial_stage: "diagnosis"`
- **THEN** the returned `SkillContent.metadata.initial_stage` contains "diagnosis"

#### Scenario: SkillContent includes stage allowed_next_stages

- **WHEN** `read_skill` is called on a skill where stage "analysis" declares `allowed_next_stages: ["execution", "abort"]`
- **THEN** the returned `SkillContent.metadata.stages` includes the "analysis" stage with its `allowed_next_stages` list

#### Scenario: SkillContent exposes terminal stage

- **WHEN** `read_skill` is called on a skill where stage "complete" declares `allowed_next_stages: []`
- **THEN** the returned `SkillContent.metadata.stages` includes the "complete" stage with an empty `allowed_next_stages` list, indicating it is terminal

### Requirement: SkillContent SHALL clearly distinguish staged vs non-staged skills

`SkillContent` MUST make it unambiguous whether a skill uses stage-based workflow or skill-level tool governance. When stages are absent, skill-level `allowed_tools` SHALL be the authoritative tool governance boundary. When stages are present, stage-level `allowed_tools` SHALL be the authoritative boundary.

#### Scenario: Non-staged skill exposes skill-level allowed_tools

- **WHEN** `read_skill` is called on a skill without stages
- **THEN** the returned `SkillContent.metadata.allowed_tools` contains the skill-level tool list and `SkillContent.metadata.stages` is empty

#### Scenario: Staged skill exposes stage-level allowed_tools

- **WHEN** `read_skill` is called on a skill with stages
- **THEN** each stage in `SkillContent.metadata.stages` contains its own `allowed_tools` list
