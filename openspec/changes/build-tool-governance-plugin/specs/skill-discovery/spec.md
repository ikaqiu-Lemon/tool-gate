## ADDED Requirements

### Requirement: List all available skills

The `list_skills` MCP tool SHALL return a list of all registered skill metadata. Each entry MUST include: `skill_id`, `name`, `description`, `risk_level`, and `is_enabled` (whether the skill is currently loaded in the session). The data source SHALL be the skill index built from scanning the `skills/` directory.

#### Scenario: List skills in a fresh session

- **WHEN** the model calls `list_skills` in a session with no skills enabled
- **THEN** the system returns all registered skills with `is_enabled: false` for each entry

#### Scenario: List skills after enabling one

- **WHEN** the model calls `list_skills` after successfully enabling skill "repo-read"
- **THEN** the system returns all registered skills, with `is_enabled: true` for "repo-read" and `is_enabled: false` for all others

#### Scenario: List skills with empty skills directory

- **WHEN** the `skills/` directory contains no valid SKILL.md files
- **THEN** the system returns an empty list with no errors

### Requirement: Read skill complete SOP

The `read_skill` MCP tool SHALL accept a `skill_id` parameter and return the skill's complete content including: metadata (all SkillMetadata fields), SOP text (Markdown body), and usage examples. The result MUST be served from cache on subsequent calls within the same session.

#### Scenario: Read an existing skill

- **WHEN** the model calls `read_skill("repo-read")`
- **THEN** the system returns the full SOP content including metadata, workflow steps, allowed_tools list, and risk information

#### Scenario: Read a nonexistent skill

- **WHEN** the model calls `read_skill("nonexistent-skill")`
- **THEN** the system returns an error response indicating the skill was not found

#### Scenario: Cache hit on repeated read

- **WHEN** the model calls `read_skill("repo-read")` twice within the TTL window (default 300s)
- **THEN** the second call returns the same result from cache without re-reading the SKILL.md file from disk

### Requirement: SKILL.md parsing with safety constraints

The skill indexer SHALL parse SKILL.md files using `yaml.safe_load` for YAML frontmatter. Files exceeding 100KB MUST be skipped. Description fields exceeding 500 characters MUST be truncated. A parse failure in one SKILL.md MUST NOT prevent other skills from being indexed.

#### Scenario: Malformed YAML frontmatter

- **WHEN** a SKILL.md file contains invalid YAML in its frontmatter
- **THEN** that skill is skipped from the index, a warning is logged, and all other valid skills are indexed normally

#### Scenario: Oversized SKILL.md file

- **WHEN** a SKILL.md file exceeds 100KB
- **THEN** the file is skipped from the index and a warning is logged

#### Scenario: Stage-aware frontmatter parsing

- **WHEN** a SKILL.md contains a `stages` field with multiple stage definitions, each specifying `stage_id`, `description`, and `allowed_tools`
- **THEN** the indexer parses all stages into `StageDefinition` objects and attaches them to the `SkillMetadata`

### Requirement: Two-layer caching

The system SHALL implement two-layer caching: (1) metadata cache at session level in `SessionState.skills_metadata`, rebuilt on new session or explicit refresh; (2) document cache at process level using TTLCache with default TTL of 300 seconds and max size of 100 entries. Cache keys MUST include a version or content hash to detect stale entries.

#### Scenario: Metadata cache persists across turns

- **WHEN** the model calls `list_skills` in turn 1 and again in turn 5 of the same session
- **THEN** both calls use the session-level metadata cache without rescanning the `skills/` directory

#### Scenario: Document cache expires after TTL

- **WHEN** the model calls `read_skill("repo-read")` and then waits longer than 300 seconds before calling again
- **THEN** the second call re-reads the SKILL.md file from disk and updates the cache

### Requirement: Refresh skills index

The `refresh_skills` MCP tool SHALL clear both the metadata cache and document cache, rescan the `skills/` directory, and rebuild the skill index. It MUST return the count of skills found after refresh.

#### Scenario: Refresh after adding a new skill file

- **WHEN** a new SKILL.md file is added to `skills/new-skill/` and the model calls `refresh_skills`
- **THEN** the system returns `{refreshed: true, skill_count: N}` where N includes the newly added skill, and subsequent `list_skills` calls include the new skill

#### Scenario: Refresh after modifying a skill file

- **WHEN** an existing SKILL.md file is modified (e.g., risk_level changed) and the model calls `refresh_skills`
- **THEN** subsequent `read_skill` calls return the updated content
