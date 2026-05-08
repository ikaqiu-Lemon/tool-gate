# Tool-Gate Project Inventory Report (v1.0.0)

**Generated**: 2026-05-06  
**Purpose**: Pre-cleanup inventory for v1.0.0 Stage-first Skill Governance release  
**Scope**: Complete directory structure analysis (374 files, 97 directories)

---

## Executive Summary

This inventory categorizes all project files to support informed cleanup decisions. The project has evolved through multiple architectural iterations, leaving behind legacy examples, temporary data, and archived OpenSpec changes. This report identifies what to keep, what to clean, and what requires user confirmation.

**Key Metrics**:
- Total size: ~700MB (467MB node_modules, 195MB .venv, ~38MB project files)
- Core runtime: 23 Python modules (src/tool_governance/)
- Tests: 290+ passing (tests/)
- Documentation: 3 root READMEs, 11 archived changes, 50+ skill files
- Examples: 3 legacy + 1 canonical (simulator-demo)

---

## Category 1: Core Runtime (KEEP)

**Purpose**: Production code for Tool-Gate governance system

### Source Code
```
src/tool_governance/
├── core/               # 8 modules (skill_manager, grant_manager, etc.)
├── models/             # 5 modules (skill, grant, stage, etc.)
├── persistence/        # 3 modules (db_manager, audit_logger, etc.)
├── indexer/            # 2 modules (skill_indexer, skill_loader)
├── mcp/                # 2 modules (server, tool_registry)
└── utils/              # 3 modules (errors, validators, etc.)
```

**Status**: ✅ Keep all  
**Rationale**: Active runtime, fully tested, referenced by CHANGELOG v1.0.0

### Tests
```
tests/
├── unit/               # 18 test modules
├── integration/        # 8 test modules
├── functional/         # 3 test modules
└── conftest.py         # Shared fixtures
```

**Status**: ✅ Keep all  
**Coverage**: ≥92% (per README.md)  
**Passing**: 290+ tests

---

## Category 2: Documentation (KEEP, with notes)

### Root Documentation
| File | Size | Status | Notes |
|------|------|--------|-------|
| `README.md` | 12KB | ✅ Keep | Updated to v1.0.0 |
| `README_CN.md` | 13KB | ✅ Keep | Synced with English version |
| `CHANGELOG.md` | 8KB | ✅ Keep | v1.0.0 entry complete |

### Project Guides
```
docs/
├── current_governance_model.md      # 15KB - Authoritative spec
├── skill_authoring_guide.md         # 12KB - For skill developers
├── openspec_workflow_guide.md       # 8KB - Change management process
└── architecture/                    # Design docs
```

**Status**: ✅ Keep all  
**Rationale**: Referenced by CHANGELOG, essential for users/contributors

### OpenSpec Archives
```
openspec/changes/archive/
├── 2026-05-03-formalize-stage-workflow-metadata/     # 88KB
├── 2026-05-04-enforce-stage-transition-governance/   # 112KB
├── 2026-05-05-migrate-demos-to-stage-first-governance/ # 84KB
└── [8 other archived changes]                        # 80-112KB each
```

**Status**: ✅ Keep all  
**Rationale**: Historical record, referenced by CHANGELOG v1.0.0  
**Note**: These are the source of truth for v1.0.0 features

### OpenSpec Specs
```
openspec/specs/
├── skill-authorization/spec.md
├── stage-transition-validation/spec.md
├── audit-observability/spec.md
└── [7 other specs]
```

**Status**: ✅ Keep all  
**Rationale**: Living specifications for governance modules

---

## Category 3: Examples (MIXED - Needs Decision)

### Canonical Demo (KEEP)
```
examples/simulator-demo/
├── scenario_01_basic_lifecycle.py
├── scenario_02_stage_transitions.py
├── scenario_03_lifecycle.py
├── reports/
│   └── scenario_03_lifecycle_showcase_report.md  # 18KB
└── skills/
    └── delivery-demo/                            # Stage-first skill
```

**Status**: ✅ Keep all  
**Rationale**: 
- Canonical demo per CHANGELOG v1.0.0
- Demonstrates Stage-first Governance
- Generates showcase report for project presentation
- All scenarios passing

### Legacy Examples (RECOMMEND ARCHIVE OR DELETE)
```
examples/01-knowledge-link/
├── start_simulation.sh
├── mcp/                    # 3 mock MCP servers
├── scripts/                # 2 Python modules
├── skills/                 # Legacy skill structure
├── logs/                   # Runtime logs
└── reports/                # Generated reports

examples/02-doc-edit-staged/
├── start_simulation.sh
├── execute_writeback.sh
├── mcp/                    # 2 mock MCP servers
├── scripts/                # 2 Python modules
├── skills/                 # Legacy skill structure
├── logs/                   # Runtime logs
└── reports/                # Generated reports

examples/03-lifecycle-and-risk/
├── start_simulation.sh
├── mcp/                    # 1 mock MCP server
├── scripts/                # 2 Python modules
├── skills/                 # Legacy skill structure
├── logs/                   # Runtime logs
└── reports/                # Generated reports
```

**Status**: ⚠️ Recommend archive or delete  
**Rationale**:
- Pre-date Stage-first Governance architecture
- Not referenced in v1.0.0 CHANGELOG
- Superseded by simulator-demo
- Contain runtime artifacts (logs/, reports/)

**Options**:
1. **Delete entirely**: If no historical value
2. **Archive to `examples/legacy/`**: If want to preserve for reference
3. **Keep**: If still used for testing/comparison

**User Decision Required**: Which option?

---

## Category 4: IDE Skill Directories (KEEP)

```
.claude/skills/         # 15 .md files
.codex/skills/          # 12 .md files
.cursor/skills/         # 11 .md files
.trae/skills/           # 12 .md files
```

**Status**: ✅ Keep all  
**Rationale**: 
- IDE-specific skill definitions
- Enable Tool-Gate integration with Claude Code, Cursor, etc.
- Small footprint (~50 files, <1MB total)

---

## Category 5: Runtime Data (CLEAN UP)

### Temporary Data Directories
| Directory | Contents | Size | Status |
|-----------|----------|------|--------|
| `.demo-data/` | governance.db | ~12KB | 🗑️ Delete |
| `data/` | governance.db | ~12KB | 🗑️ Delete |
| `.scenario-03-data/` | governance.db, events.jsonl, metrics.json, audit_summary.md | ~20KB | 🗑️ Delete |

**Rationale**: 
- Generated by example runs
- Not tracked in git
- Can be regenerated by running scenarios
- Should be in .gitignore

**Action**: Delete all, verify .gitignore covers them

### Example Runtime Artifacts
```
examples/01-knowledge-link/logs/
examples/01-knowledge-link/reports/
examples/02-doc-edit-staged/logs/
examples/02-doc-edit-staged/reports/
examples/03-lifecycle-and-risk/logs/
examples/03-lifecycle-and-risk/reports/
```

**Status**: 🗑️ Delete (if examples are kept, these should be regenerated)  
**Rationale**: Runtime artifacts, not source code

---

## Category 6: Dependencies (KEEP)

```
node_modules/           # 467MB - npm dependencies
.venv/                  # 195MB - Python virtual environment
```

**Status**: ✅ Keep (but not in git)  
**Rationale**: Standard dependency directories, covered by .gitignore

---

## Category 7: Configuration & Build (KEEP)

```
Root files:
├── pyproject.toml          # Python project config
├── package.json            # npm config (OpenSpec tooling)
├── package-lock.json       # npm lockfile
├── pytest.ini              # Test configuration
├── .gitignore              # Git ignore rules
└── .python-version         # Python version pin
```

**Status**: ✅ Keep all  
**Rationale**: Essential for build/test/development

---

## Category 8: Reports (KEEP)

```
reports/
└── scenario_03_lifecycle_showcase_report.md  # 18KB
```

**Status**: ✅ Keep  
**Rationale**: 
- Generated from canonical demo
- Suitable for project presentation
- Referenced in v1.0.0 release context

---

## Recommendations Summary

### Immediate Actions (Safe to Execute)
1. **Delete runtime data directories**:
   ```bash
   rm -rf .demo-data/ data/ .scenario-03-data/
   ```

2. **Verify .gitignore coverage**:
   ```
   .demo-data/
   data/
   .scenario-*-data/
   examples/*/logs/
   examples/*/reports/
   *.db
   *.jsonl
   ```

### User Decisions Required

**Decision 1: Legacy Examples**
- **Option A**: Delete `examples/01-knowledge-link/`, `examples/02-doc-edit-staged/`, `examples/03-lifecycle-and-risk/`
- **Option B**: Move to `examples/legacy/` for historical reference
- **Option C**: Keep as-is

**Recommendation**: Option A (delete) - they predate v1.0.0 architecture and are superseded by simulator-demo

**Decision 2: OpenSpec Archives**
- Current: 11 archived changes (80-112KB each, ~1MB total)
- **Option A**: Keep all (historical record)
- **Option B**: Keep only v1.0.0-related (3 changes: formalize-stage-workflow-metadata, enforce-stage-transition-governance, migrate-demos-to-stage-first-governance)
- **Option C**: Compress to single archive file

**Recommendation**: Option A (keep all) - disk space is not a concern, and they document project evolution

---

## Post-Cleanup Expected State

**Core Project** (~40MB):
```
tool-gate/
├── src/                    # 23 modules
├── tests/                  # 29 test modules
├── docs/                   # 4 guides + architecture/
├── examples/
│   └── simulator-demo/     # Canonical demo only
├── openspec/               # Specs + archived changes
├── reports/                # Showcase reports
├── .claude/                # IDE skills
├── .codex/
├── .cursor/
├── .trae/
└── [config files]
```

**Dependencies** (~662MB, not in git):
```
├── node_modules/           # 467MB
└── .venv/                  # 195MB
```

**Total tracked files**: ~250 (down from 374)  
**Total tracked size**: ~40MB (down from ~700MB including deps)

---

## Verification Checklist

After cleanup:
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Simulator-demo runs: `python examples/simulator-demo/scenario_03_lifecycle.py`
- [ ] Documentation builds: Check all .md files render correctly
- [ ] Git status clean: `git status` shows no unexpected deletions
- [ ] .gitignore effective: Runtime artifacts not tracked

---

## Notes

- This report is **analysis only** - no files have been modified
- All recommendations preserve v1.0.0 release integrity
- Legacy examples can be recovered from git history if needed
- Runtime data directories can be regenerated by running scenarios
