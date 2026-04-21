# skill-discovery Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
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

The system SHALL maintain two cache layers — one for skill metadata (frontmatter-derived index entries) and one for skill document content (parsed SOP text) — that MUST share a single explicit cache contract: every entry MUST be addressable by a key that binds the skill identifier to the skill's current version, MUST honor a configurable time-to-live and size limit, and MUST expose both per-entry invalidation and whole-cache invalidation. Neither layer MAY be an implicit internal structure of the discovery component; both MUST participate in the same cache contract so that operators reason about one cache surface, not two. The session-level skill snapshot remains a distinct concept from the metadata cache and is unaffected by this contract.

#### Scenario: Repeated catalog listing within one session hits the formal cache

- **WHEN** the model lists the skill catalog twice within the same session and no skill version has changed
- **THEN** the second listing is satisfied from the metadata cache without rescanning skill files or reparsing frontmatter

#### Scenario: Metadata and document entries honor a common invalidation surface

- **WHEN** invalidation is triggered against a specific skill identifier
- **THEN** both the metadata entry and the document entry for that skill are removed, and subsequent lookups for that skill rebuild from disk

#### Scenario: Document cache expires after TTL

- **WHEN** a skill document is read and then read again after its TTL window has elapsed
- **THEN** the later read rebuilds the document from disk rather than returning the expired cached value

### Requirement: Refresh skills index

The refresh operation SHALL invalidate every cache entry populated by prior scans before rebuilding the index, and MUST return the count of skills found after rebuild. Metadata entries and document entries MUST be cleared within the same refresh call; no entry populated before the refresh MAY satisfy a lookup that completes after the refresh returns.

#### Scenario: Refresh removes stale document entries

- **WHEN** an existing skill document is modified on disk and refresh is triggered
- **THEN** the next document read returns the modified content rather than the pre-refresh cached version

#### Scenario: Refresh removes stale metadata entries

- **WHEN** an existing skill's frontmatter is modified on disk and refresh is triggered
- **THEN** the next catalog listing reflects the modified metadata rather than the pre-refresh cached version

#### Scenario: Refresh surfaces the post-rebuild skill count

- **WHEN** the catalog previously contained N skills, a new skill is added on disk, and refresh is triggered
- **THEN** the refresh response reports a skill count that includes the newly added skill

### Requirement: Cache is a performance layer, not a source of truth

The cache subsystem SHALL be treated as a performance optimization whose sole purpose is to avoid redundant I/O and parsing. It MUST NOT be the authoritative source of any skill metadata or document content: every cached value MUST be reproducible by rereading the underlying skill file on disk. Governance decisions — authorization, tool-surface composition, and audit — MUST NOT branch on whether a value came from cache or from disk; the cached path and the rebuilt path MUST produce identical observable outcomes.

#### Scenario: Cache loss does not change governance behavior

- **WHEN** the entire cache is cleared mid-session and the model subsequently lists the catalog and then reads a specific skill
- **THEN** the responses are identical in content to those that would have been returned with a populated cache, differing only in latency

#### Scenario: Cached and rebuilt values are interchangeable

- **WHEN** the same skill is read once via a cache hit and once via a cache miss that rebuilds from disk
- **THEN** the two responses contain identical parsed content and drive identical downstream authorization and tool-surface composition

### Requirement: Version change invalidates prior cache entries

The system SHALL ensure that when a skill's declared version changes, any cache entry keyed to the older version becomes unreachable for subsequent lookups. The system MUST NOT return a value derived from an older version of a skill once that skill's version has advanced on disk, regardless of whether the TTL window for the older entry has elapsed.

#### Scenario: Version bump supersedes a cached document

- **WHEN** a skill document is cached, the skill's declared version is incremented on disk, and the document is requested again within the TTL window
- **THEN** the system returns content derived from the new version, not the pre-increment cached content

#### Scenario: Version bump supersedes a cached metadata entry

- **WHEN** a skill's frontmatter is cached, the skill's declared version is incremented on disk, and the catalog is listed again within the TTL window
- **THEN** the listing reflects the new metadata for that skill rather than the pre-increment cached entry

### Requirement: Safe fallback on cache miss, invalidation, or refresh failure

The system SHALL rebuild any missing value from the underlying skill files on disk whenever a lookup misses the cache, an entry is invalidated, or a refresh operation fails. A refresh failure MUST NOT leave callers unable to list or read skills when the underlying files are still readable. When rebuild-from-disk itself is not possible — for example, because the source file is unreadable — the system MUST return a structured error identifying the failing source rather than a stale cached value presented as fresh.

#### Scenario: Cache miss triggers a clean rebuild

- **WHEN** a lookup targets a key that is not present in the cache
- **THEN** the system reads the underlying skill file, returns the parsed value to the caller, and populates the cache for subsequent lookups

#### Scenario: Refresh failure degrades safely

- **WHEN** a refresh operation fails partway because one or more skill files are temporarily unreadable and the caller subsequently requests the catalog
- **THEN** the system returns either the successfully rebuilt subset together with a structured error identifying the failing source, or a structured error when no subset could be rebuilt — never a pre-refresh cached entry presented as fresh

