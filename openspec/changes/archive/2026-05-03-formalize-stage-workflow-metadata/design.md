## Context

### Current State

The codebase already has foundational stage support:

**Existing Models** (`src/tool_governance/models/skill.py`):
- `StageDefinition`: Defines `stage_id`, `description`, `allowed_tools`
- `SkillMetadata`: Contains `stages: list[StageDefinition]`, `allowed_tools` (skill-level fallback)
- `SkillContent`: Returned by `read_skill`, contains `metadata` and `sop`

**Existing Runtime** (`src/tool_governance/core/`):
- `SkillIndexer.read_skill()`: Parses SKILL.md, returns `SkillContent` with metadata + SOP
- `ToolRewriter.get_stage_tools(skill_meta, current_stage)`: Resolves tools based on stage
- `LoadedSkillInfo.current_stage`: Tracks active stage per enabled skill

**Current Behavior**:
- Skills can define stages with stage-level `allowed_tools`
- `get_stage_tools` falls back to skill-level `allowed_tools` when no stages defined
- `change_stage` MCP tool exists but has no transition validation
- No formal `initial_stage` field
- No formal `allowed_next_stages` field
- No authoring standard document

### Problem

1. **Metadata gaps**: No formal `initial_stage` or `allowed_next_stages` fields
2. **Semantic ambiguity**: Terminal stages have no standard representation
3. **Missing guidance**: No authoring standard for when/how to decompose Skills into Stages
4. **Skill misunderstanding**: Risk of treating Skills as "tool groups" rather than "business workflows"

### Constraints

- **No breaking changes**: Existing skills without stages must continue working
- **No runtime enforcement**: This change defines metadata/schema only; runtime state machine (auto-enter initial_stage, validate transitions) is deferred
- **Minimal surface**: Only extend models, update read_skill output, add authoring doc

## Goals / Non-Goals

**Goals:**
1. Formalize `initial_stage` and `allowed_next_stages` in metadata schema
2. Ensure `SkillContent` / `read_skill` expose complete stage workflow information
3. Create `docs/skill_stage_authoring.md` defining Skill/Stage decomposition standards
4. Preserve backward compatibility for skills without stages
5. Establish semantic foundation for future runtime enforcement

**Non-Goals:**
1. Implement `enable_skill` auto-entry to `initial_stage`
2. Implement `change_stage` validation of `allowed_next_stages`
3. Implement `exited_stages` / `stage_history` / `stage_entered_at` state tracking
4. Migrate `simulator-demo` or deprecate old examples
5. Modify `RuntimeContext` or hook handlers

## Decisions

### Decision 1: Extend StageDefinition with allowed_next_stages

**Choice**: Add `allowed_next_stages: list[str] = Field(default_factory=list)` to `StageDefinition`

**Rationale**:
- Encodes valid workflow transitions at metadata level
- Empty list (`[]`) naturally represents terminal stage
- Non-breaking: existing stages without this field default to empty list
- Enables future runtime validation without schema migration

**Alternatives considered**:
- **Separate TerminalStage model**: Rejected; adds complexity, breaks uniform stage handling
- **String enum for stage types**: Rejected; less flexible than explicit successor list

**Implementation**:
```python
class StageDefinition(BaseModel):
    stage_id: str
    description: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_next_stages: list[str] = Field(default_factory=list)  # NEW
```

### Decision 2: Extend SkillMetadata with initial_stage

**Choice**: Add `initial_stage: str | None = None` to `SkillMetadata`

**Rationale**:
- Explicit workflow entry point
- `None` means "default to first stage" (existing behavior)
- Non-breaking: existing skills without this field get `None`
- Enables future auto-entry without schema migration

**Alternatives considered**:
- **Always require initial_stage when stages exist**: Rejected; too strict, breaks existing skills
- **Derive initial_stage from stage order**: Current behavior; explicit field is clearer

**Implementation**:
```python
class SkillMetadata(BaseModel):
    skill_id: str
    name: str
    description: str = ""
    risk_level: Literal["low", "medium", "high"] = "low"
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_ops: list[str] = Field(default_factory=list)
    stages: list[StageDefinition] = Field(default_factory=list)
    initial_stage: str | None = None  # NEW
    default_ttl: int = 3600
    source_path: str = ""
    version: str = "1.0.0"
```

### Decision 3: SkillContent returns metadata as-is, no derived summary

**Choice**: `SkillContent` already contains `metadata: SkillMetadata`. With extended schema, it automatically exposes `initial_stage` and `allowed_next_stages`.

**Rationale**:
- Zero code change needed in `SkillIndexer.read_skill()`
- Pydantic serialization automatically includes new fields
- Model sees complete workflow structure via metadata
- No risk of derived summary diverging from source metadata

**Alternatives considered**:
- **Add workflow_summary field**: Rejected; redundant, adds maintenance burden
- **Flatten stage info to top level**: Rejected; breaks existing SkillContent consumers

**Implementation**: No change to `SkillContent` or `read_skill()` logic. Schema extension is sufficient.

### Decision 4: Authoring doc structure

**Choice**: Create `docs/skill_stage_authoring.md` with the following structure:

```markdown
# Skill Stage Authoring Standard

## 1. Core Definitions
- Skill = business capability / SOP / workflow
- Stage = phase within a Skill's workflow
- Tool = external capability callable within a stage

## 2. When to Create a Skill
- Represents a coherent business capability
- Has a clear SOP (standard operating procedure)
- NOT just a tool grouping

## 3. When to Decompose into Stages
- Workflow has distinct phases with different tool requirements
- Different phases have different risk profiles
- Progressive disclosure needed (read-only → read-write)

## 4. When NOT to Use Stages
- Simple, uniform workflow
- Low-risk, single-phase operation
- Tool requirements don't change across workflow

## 5. Choosing initial_stage
- Should be safest entry point (typically read-only)
- Must be a valid stage_id from stages list
- If omitted, first stage is default

## 6. Designing allowed_next_stages
- List valid successor stage_ids
- Empty list [] = terminal stage
- Circular/backward transitions allowed for retry patterns

## 7. Anti-Patterns
- ❌ Splitting by tool type ("read-stage", "write-stage")
- ❌ Creating separate skills for "read-ops" and "write-ops"
- ✅ Splitting by workflow phase ("diagnose", "analyze", "remediate")

## 8. Examples
### Example 1: Simple Skill (no stages)
### Example 2: Staged Skill (document editing workflow)
```

**Rationale**:
- Prescriptive guidance prevents tool-centric decomposition
- Examples ground abstract principles
- Clear anti-patterns prevent common mistakes

### Decision 5: Validation warnings, not errors

**Choice**: When parsing SKILL.md:
- `initial_stage` references non-existent stage → log warning, set to `None`
- `allowed_next_stages` references non-existent stage → log warning, keep list as-is
- `initial_stage` present but no stages → log warning, ignore field

**Rationale**:
- Fail-soft: one bad skill doesn't break entire index
- Warnings visible in logs for debugging
- Runtime can handle `None` / invalid references gracefully

**Alternatives considered**:
- **Strict validation, reject skill**: Rejected; too brittle, breaks discovery
- **Silent ignore**: Rejected; hides authoring errors

## Risks / Trade-offs

### Risk 1: Metadata divergence from runtime behavior

**Risk**: `initial_stage` and `allowed_next_stages` are declared but not enforced until future change.

**Mitigation**:
- Authoring doc explicitly states "metadata only, runtime enforcement TBD"
- Tests verify metadata parsing, not runtime enforcement
- Future change (`enforce-stage-transition-governance`) will implement enforcement

### Risk 2: Invalid stage references in allowed_next_stages

**Risk**: Author declares `allowed_next_stages: ["nonexistent"]`, causing confusion.

**Mitigation**:
- Validation warnings logged during indexing
- Authoring doc includes validation checklist
- Future runtime enforcement will deny invalid transitions

### Risk 3: Authoring doc out of sync with code

**Risk**: Doc describes behavior not yet implemented, or contradicts actual behavior.

**Mitigation**:
- Doc explicitly marks "metadata-only" vs "future runtime"
- Tests verify doc examples parse correctly
- Doc review as part of change acceptance

### Risk 4: Breaking existing skills

**Risk**: Schema changes break existing SKILL.md files.

**Mitigation**:
- All new fields are optional with safe defaults
- Existing skills without `initial_stage` / `allowed_next_stages` continue working
- Test suite includes backward compatibility cases

## Implementation Plan

### Phase 1: Schema Extension

**Files to modify**:
- `src/tool_governance/models/skill.py`:
  - Add `initial_stage: str | None = None` to `SkillMetadata`
  - Add `allowed_next_stages: list[str] = Field(default_factory=list)` to `StageDefinition`

**No changes needed**:
- `SkillContent`: Already contains `metadata`, automatically exposes new fields
- `SkillIndexer.read_skill()`: Pydantic handles new fields automatically
- `SkillIndexer._parse_skill_file()`: YAML parsing already handles optional fields

### Phase 2: Validation Warnings

**Files to modify**:
- `src/tool_governance/core/skill_indexer.py`:
  - In `_parse_skill_file()`, after parsing metadata:
    - If `initial_stage` is not None and not in `[s.stage_id for s in metadata.stages]`, log warning
    - If `initial_stage` is not None and `stages` is empty, log warning
    - For each stage, if `allowed_next_stages` contains stage_id not in stages list, log warning

### Phase 3: Authoring Documentation

**Files to create**:
- `docs/skill_stage_authoring.md`: Full authoring standard per Decision 4 structure

**Content requirements**:
- Define Skill/Stage/Tool semantics
- When to use stages vs skill-level allowed_tools
- How to choose initial_stage
- How to design allowed_next_stages
- Terminal stage representation (`[]`)
- Anti-patterns (tool-centric decomposition)
- Two examples: simple skill, staged skill

### Phase 4: Testing

**Test files to create/modify**:
- `tests/test_skill_indexer.py`:
  - Test parsing `initial_stage` from frontmatter
  - Test parsing `allowed_next_stages` from frontmatter
  - Test `allowed_next_stages: []` preserved as empty list
  - Test skills without stages remain valid
  - Test validation warnings for invalid stage references
- `tests/test_models.py`:
  - Test `SkillMetadata` with `initial_stage`
  - Test `StageDefinition` with `allowed_next_stages`
  - Test backward compatibility (fields optional)
- `tests/test_integration.py`:
  - Test `read_skill` returns staged skill with complete workflow info
  - Test `read_skill` returns non-staged skill with skill-level allowed_tools

**Out of scope for testing**:
- `enable_skill` auto-entry to `initial_stage`
- `change_stage` validation of `allowed_next_stages`
- `exited_stages` / `stage_history` persistence

## Interface Reservations for Future Changes

This change establishes metadata semantics that future changes will enforce at runtime:

### Reserved for `enforce-stage-transition-governance` change:

1. **enable_skill auto-entry**:
   - When `initial_stage` is not None, `enable_skill` should set `LoadedSkillInfo.current_stage = initial_stage`
   - When `initial_stage` is None and stages exist, set `current_stage = stages[0].stage_id`

2. **change_stage validation**:
   - Before transitioning, check if target stage is in `current_stage.allowed_next_stages`
   - If not, return deny with `error_bucket: invalid_stage_transition`
   - If skill has no stages, return deny with `error_bucket: skill_has_no_stages`

3. **State tracking**:
   - `LoadedSkillInfo.exited_stages: list[str]` - stages left during this session
   - `LoadedSkillInfo.stage_entered_at: datetime` - when current stage was entered
   - Audit events: `stage.enter`, `stage.exit`, `stage.transition.deny`

4. **Terminal stage handling**:
   - When `current_stage.allowed_next_stages == []`, `change_stage` to any stage returns deny
   - Error message: "Current stage is terminal; no further transitions permitted"

## Migration Strategy

### Backward Compatibility

**Existing skills without stages**:
- Continue using `skill.allowed_tools`
- No migration needed
- Remain fully supported format

**Existing skills with stages**:
- `initial_stage` defaults to `None` (first stage is entry)
- `allowed_next_stages` defaults to `[]` (all stages effectively terminal until explicitly declared)
- No breaking changes

### Rollback Plan

If this change causes issues:

1. **Schema rollback**: Remove `initial_stage` and `allowed_next_stages` fields from models
2. **Doc rollback**: Remove `docs/skill_stage_authoring.md`
3. **Test rollback**: Remove new test cases

**Risk**: Low. Schema changes are additive and optional. No runtime behavior changes.

## Open Questions

None. All design decisions are finalized based on proposal and specs.
