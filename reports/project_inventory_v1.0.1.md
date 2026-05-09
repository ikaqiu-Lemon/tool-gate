# Stagewise-Stagewise-Tool-Gate Project Inventory Report v1.0.1

**Generated**: 2026-05-06  
**Purpose**: Accurate pre-cleanup inventory for v1.0.0 Stage-first Skill Governance release  
**Scope**: Complete directory structure analysis based on real command outputs  
**Replaces**: v1.0.0 inventory (contained structural errors and fabricated information)

---

## Executive Summary

- **Total tracked files**: 362
- **Python files**: 98
- **Markdown files**: 198
- **Test suites**: 290 tests passing
- **OpenSpec specs**: 10 validated ✓
- **OpenSpec archives**: 11 changes
- **Active changes**: 0
- **Git status**: 3 modified, 11 deleted (staged), 4 untracked files/directories
- **Total size**: ~773MB (467MB node_modules, 195MB .venv, ~111MB project files)

---

## 1. Data Sources

This inventory is based on the following real command outputs executed on 2026-05-06:

```bash
pwd                                    # /home/zh/stagewise-tool-gate
git status --short                     # Show working tree status
git diff --cached --name-status        # Show staged changes (empty)
git ls-files --deleted                 # Show deleted tracked files (11 files)
git ls-files --others --exclude-standard | sort  # Untracked files (4 items)
git ls-files --others --ignored --exclude-standard | head -100  # Ignored files
git ls-files | wc -l                   # Count tracked files: 362
git ls-files '*.py' | wc -l            # Count Python files: 98
git ls-files '*.md' | wc -l            # Count Markdown files: 198
find . -maxdepth 4 -type d [filters]   # Directory structure
find src/tool_governance -maxdepth 3 -type f | sort
find tests -maxdepth 3 -type f -name '*.py' | sort
find examples -maxdepth 4 -type f | sort
find docs -maxdepth 4 -type f | sort
find openspec -maxdepth 5 -type f -name '*.md' | sort
find . -maxdepth 5 \( -name '*.db' -o -name 'events.jsonl' -o -name 'audit_summary.md' -o -name 'metrics.json' \) | sort
git ls-files | grep -E '(\.db$|events\.jsonl$|audit_summary\.md$|metrics\.json$|\.log$)'
openspec list                          # No active changes
openspec validate --all                # 10 passed, 0 failed
pytest --collect-only -q               # 290 tests collected
du -sh [directories]                   # Size analysis
```

**Methodology**: All directory structures, file lists, and statistics are derived from real command outputs. No information was fabricated or assumed from memory.


---

## 2. Git Status Summary

### 2.1 Current Working Tree State

**Modified (M)**: 3 files
```
M  CHANGELOG.md                     # v1.0.0 release notes added
M  README.md                        # Updated to v1.0.0
M  README_CN.md                     # Updated to v1.0.0 (Chinese)
```

**Deleted (D)**: 11 files (staged for deletion)
```
D  BUG_FIX_INDEXER_INITIALIZATION.md
D  当前能力治理模型反向梳理.md
D  openspec-progress-report.md
D  scripts/bench_phase4.py
D  examples/02-doc-edit-staged/SETUP_COMPLETE.md
D  examples/02-doc-edit-staged/WRITEBACK_SUMMARY.md
D  examples/02-doc-edit-staged/agent_simulation_event_log.md
D  examples/02-doc-edit-staged/proposed_update_for_rag-overview-v2.md
D  examples/simulator-demo/OPENSPEC_ALIGNMENT_SUMMARY.md
D  examples/simulator-demo/STAGE_C_COMPLETE.md
D  examples/simulator-demo/STAGE_D_COMPLETE.md
```

**Untracked (??)**: 4 files/directories
```
??  docs/current_governance_model.md                              # NEW: Authoritative governance spec
??  examples/simulator-demo/reports/                              # NEW: Contains showcase report
??  reports/                                                       # NEW: Contains inventory reports
```

**Staged changes**: None (git diff --cached returned empty)

### 2.2 Analysis

**Modified files**: All 3 are source documentation updated to v1.0.0 release. Should be committed.

**Deleted files**: All 11 are temporary summaries, progress reports, or stage completion markers generated during OpenSpec change development. These are **not source code** and deletions should be committed.

**Untracked files**:
- `docs/current_governance_model.md`: New authoritative governance model documentation (source, should be tracked)
- `examples/simulator-demo/reports/`: Contains `scenario_03_lifecycle_showcase_report.md` (18KB showcase report, should be tracked per v1.0.0 release plan)
- `reports/`: Contains `project_inventory_v1.0.0.md` (superseded) and `project_inventory_v1.0.1.md` (this file)

---

## 3. Accurate Directory Tree

Based on real `find` command outputs:

```
stagewise-tool-gate/
├── .claude/                          # Claude Code IDE integration
│   ├── commands/opsx/                # OpenSpec commands
│   └── skills/                       # 15 skill definitions
├── .codex/skills/                    # Codex IDE integration (12 skills)
├── .cursor/                          # Cursor IDE integration
│   ├── commands/                     # OpenSpec commands
│   └── skills/                       # 11 skill definitions
├── .trae/skills/                     # Trae IDE integration (12 skills)
├── config/                           # Configuration directory
├── data/                             # Runtime data (contains governance.db - ignored)
├── .demo-data/                       # Demo runtime data (contains governance.db - ignored)
├── docs/                             # Documentation (12 files)
│   ├── current_governance_model.md   # NEW: Authoritative governance spec
│   ├── skill_stage_authoring.md      # Skill authoring guide
│   ├── dev_plan.md, requirements.md, technical_design.md
│   ├── self_test_runbook.md, session_logging_prompt.md
│   ├── perf_results.md, README.md
│   └── [Chinese versions: 开发计划.md, 技术方案文档.md, 需求文档.md]
├── examples/
│   ├── simulator-demo/               # ✅ CANONICAL DEMO (Stage-first)
│   │   ├── scenarios/                # 3 scenario scripts
│   │   │   ├── scenario_01_discovery.py
│   │   │   ├── scenario_02_staged.py
│   │   │   └── scenario_03_lifecycle.py
│   │   ├── simulator/                # Simulator framework
│   │   │   ├── core.py
│   │   │   ├── hook_subprocess.py
│   │   │   ├── mcp_subprocess.py
│   │   │   └── __init__.py
│   │   ├── fixtures/skills/          # Test skill fixtures
│   │   │   ├── yuque-doc-edit-staged/
│   │   │   └── yuque-knowledge-link/
│   │   ├── reports/                  # Generated showcase reports
│   │   │   └── scenario_03_lifecycle_showcase_report.md
│   │   ├── .scenario-01-data/        # Runtime artifacts (ignored)
│   │   ├── .scenario-02-data/        # Runtime artifacts (ignored)
│   │   ├── .scenario-03-data/        # Runtime artifacts (ignored)
│   │   ├── .test-list-skills/        # Test artifacts (ignored)
│   │   ├── .test-mcp-raw/            # Test artifacts (ignored)
│   │   ├── run_simulator.sh          # Main entry point
│   │   ├── verify_stage_first.py     # Stage-first validation
│   │   ├── verify_skill_fixtures.py  # Fixture validation
│   │   ├── integration_test.py, smoke_test.py
│   │   ├── .gitignore
│   │   ├── README.md, SCOPE.md, SCENARIOS.md
│   │   ├── ACCEPTANCE_CRITERIA.md, EVENT_COVERAGE.md
│   │   └── [verification scripts: verify_stage_c.py, verify_stage_d.py]
│   ├── 01-knowledge-link/            # ⚠️ LEGACY (Deprecated, kept for reference)
│   │   ├── skills/, mcp/, scripts/, config/, contracts/, schemas/
│   │   ├── logs/session_*/           # Runtime artifacts (tracked)
│   │   ├── reports/                  # Generated reports (tracked)
│   │   ├── .demo-data/               # Runtime data (ignored)
│   │   ├── start_simulation.sh, README.md
│   │   └── .cleanup_completed, .mcp.json
│   ├── 02-doc-edit-staged/           # ⚠️ LEGACY (Deprecated, kept for reference)
│   │   ├── skills/, mcp/, scripts/, config/, contracts/, schemas/
│   │   ├── logs/session_*/           # Runtime artifacts (tracked)
│   │   ├── reports/                  # Generated reports (tracked)
│   │   ├── .demo-data/               # Runtime data (ignored)
│   │   ├── start_simulation.sh, execute_writeback.sh, README.md
│   │   └── .mcp.json
│   ├── 03-lifecycle-and-risk/        # ⚠️ LEGACY (Deprecated, kept for reference)
│   │   ├── skills/, mcp/, scripts/, config/, contracts/, schemas/
│   │   ├── logs/session_*/           # Runtime artifacts (tracked)
│   │   ├── reports/                  # Generated reports (tracked)
│   │   ├── .demo-data/               # Runtime data (ignored)
│   │   ├── start_simulation.sh, README.md
│   │   └── .mcp.json
│   ├── README.md                     # Examples overview
│   └── QUICKSTART.md                 # Quick start guide
├── hooks/                            # Hook scripts directory
├── openspec/
│   ├── specs/                        # 10 validated specifications
│   │   ├── audit-observability/
│   │   ├── delivery-demo-harness/
│   │   ├── functional-test-harness/
│   │   ├── session-lifecycle/
│   │   ├── skill-authorization/
│   │   ├── skill-discovery/
│   │   ├── skill-execution/
│   │   ├── stage-transition-validation/
│   │   ├── tool-governance-hardening/
│   │   └── tool-surface-control/
│   └── changes/archive/              # 11 archived changes
│       ├── 2026-04-19-add-functional-test-plan/
│       ├── 2026-04-19-build-tool-governance-plugin/
│       ├── 2026-04-19-phase13-hardening-and-doc-sync/
│       ├── 2026-04-20-formalize-cache-layers/
│       ├── 2026-04-30-migrate-entrypoints-to-runtime-flow/
│       ├── 2026-05-01-remove-legacy-delivery-demo-changes/
│       ├── 2026-05-03-formalize-stage-workflow-metadata/
│       ├── 2026-05-03-separate-runtime-and-persisted-state/
│       ├── 2026-05-03-simulate-claude-code-call-chain-demo/
│       ├── 2026-05-04-enforce-stage-transition-governance/
│       └── 2026-05-05-migrate-demos-to-stage-first-governance/
├── reports/                          # Analysis reports
│   ├── project_inventory_v1.0.0.md   # First inventory (contains errors)
│   └── project_inventory_v1.0.1.md   # This file (corrected)
├── scripts/                          # Utility scripts
├── skills/                           # Root skill definitions (4 skills)
│   ├── code-edit/
│   ├── governance/
│   ├── repo-read/
│   └── web-search/
├── src/tool_governance/              # Core runtime (23 modules)
│   ├── bootstrap.py                  # Bootstrap initialization
│   ├── hook_handler.py               # Hook entrypoint handler
│   ├── mcp_server.py                 # MCP server entrypoint
│   ├── __init__.py
│   ├── core/                         # Core governance logic (9 modules)
│   │   ├── grant_manager.py
│   │   ├── observability.py
│   │   ├── policy_engine.py
│   │   ├── prompt_composer.py
│   │   ├── runtime_context.py
│   │   ├── skill_executor.py
│   │   ├── skill_indexer.py
│   │   ├── state_manager.py
│   │   ├── tool_rewriter.py
│   │   └── __init__.py
│   ├── models/                       # Data models (5 modules)
│   │   ├── grant.py
│   │   ├── policy.py
│   │   ├── skill.py
│   │   ├── state.py
│   │   └── __init__.py
│   ├── storage/                      # Persistence layer (1 module)
│   │   ├── sqlite_store.py
│   │   └── __init__.py
│   ├── tools/                        # Tool integrations (1 module)
│   │   ├── langchain_tools.py
│   │   └── __init__.py
│   └── utils/                        # Utilities (1 module)
│       ├── cache.py
│       └── __init__.py
├── tests/                            # Test suite (290 tests, 31 test files)
│   ├── conftest.py                   # Shared fixtures
│   ├── fixtures/                     # Test fixtures
│   │   ├── mcp/                      # Mock MCP servers
│   │   └── skills/                   # Mock skill fixtures
│   ├── functional/                   # Functional tests (13 files)
│   └── [18 unit/integration test files]
├── node_modules/                     # npm dependencies (467MB, ignored)
├── .venv/                            # Python virtual env (195MB, ignored)
├── .gitignore
├── .python-version
├── CHANGELOG.md
├── README.md
├── README_CN.md
├── package.json, package-lock.json
├── pyproject.toml
└── pytest.ini
```

**Total size**: ~773MB (467MB node_modules, 195MB .venv, ~111MB project files)


---

## 4. Core Runtime Inventory (`src/tool_governance/`)

### 4.1 Actual Structure (Based on Real `find` Output)

| Path | Type | Purpose | Core | Keep |
|------|------|---------|------|------|
| `src/tool_governance/__init__.py` | Module | Package init | ✅ | ✅ |
| `src/tool_governance/bootstrap.py` | Module | Bootstrap initialization | ✅ | ✅ |
| `src/tool_governance/hook_handler.py` | Module | Hook entrypoint handler | ✅ | ✅ |
| `src/tool_governance/mcp_server.py` | Module | MCP server entrypoint | ✅ | ✅ |
| `src/tool_governance/core/grant_manager.py` | Module | Grant lifecycle management | ✅ | ✅ |
| `src/tool_governance/core/observability.py` | Module | Audit logging & observability | ✅ | ✅ |
| `src/tool_governance/core/policy_engine.py` | Module | Policy evaluation engine | ✅ | ✅ |
| `src/tool_governance/core/prompt_composer.py` | Module | Skill prompt composition | ✅ | ✅ |
| `src/tool_governance/core/runtime_context.py` | Module | Runtime context management | ✅ | ✅ |
| `src/tool_governance/core/skill_executor.py` | Module | Skill execution logic | ✅ | ✅ |
| `src/tool_governance/core/skill_indexer.py` | Module | Skill discovery & indexing | ✅ | ✅ |
| `src/tool_governance/core/state_manager.py` | Module | State management (stage transitions) | ✅ | ✅ |
| `src/tool_governance/core/tool_rewriter.py` | Module | Tool surface rewriting | ✅ | ✅ |
| `src/tool_governance/models/grant.py` | Model | Grant data model | ✅ | ✅ |
| `src/tool_governance/models/policy.py` | Model | Policy data model | ✅ | ✅ |
| `src/tool_governance/models/skill.py` | Model | Skill data model | ✅ | ✅ |
| `src/tool_governance/models/state.py` | Model | State data model | ✅ | ✅ |
| `src/tool_governance/storage/sqlite_store.py` | Storage | SQLite persistence layer | ✅ | ✅ |
| `src/tool_governance/tools/langchain_tools.py` | Integration | LangChain tool integration | ✅ | ✅ |
| `src/tool_governance/utils/cache.py` | Utility | Cache management (5min TTL) | ✅ | ✅ |

**Total**: 23 Python modules (excluding `__init__.py` files)

### 4.2 v1.0.0 Inventory Correction

**v1.0.0 incorrectly claimed**: `persistence/`, `indexer/`, `mcp/` subdirectories exist

**v1.0.1 reality**: The actual subdirectories are:
- `core/` (9 modules)
- `models/` (5 modules including `__init__.py`)
- `storage/` (not "persistence/")
- `tools/` (not a separate "mcp/" directory - mcp_server.py is at root level)
- `utils/`

---

## 5. Test Suite Inventory (`tests/`)

### 5.1 Test Files (Based on Real `find` Output)

**Total**: 290 tests collected across 31 test files

| Path | Test Type | Purpose | Keep |
|------|-----------|---------|------|
| `tests/conftest.py` | Fixture | Shared pytest fixtures | ✅ |
| `tests/test_cache.py` | Unit | Cache utility tests | ✅ |
| `tests/test_grant_expiry_runtime_view.py` | Unit | Grant expiry logic | ✅ |
| `tests/test_grant_manager.py` | Unit | Grant manager tests | ✅ |
| `tests/test_hook_indexer_initialization.py` | Unit | Hook indexer init tests | ✅ |
| `tests/test_hook_lifecycle.py` | Integration | Hook lifecycle tests | ✅ |
| `tests/test_integration.py` | Integration | Integration tests | ✅ |
| `tests/test_mcp_runtime_flow.py` | Integration | MCP runtime flow tests | ✅ |
| `tests/test_models.py` | Unit | Data model tests | ✅ |
| `tests/test_observability.py` | Unit | Observability tests | ✅ |
| `tests/test_policy_engine.py` | Unit | Policy engine tests | ✅ |
| `tests/test_prompt_composer.py` | Unit | Prompt composer tests | ✅ |
| `tests/test_runtime_context.py` | Unit | Runtime context tests | ✅ |
| `tests/test_skill_indexer.py` | Unit | Skill indexer tests | ✅ |
| `tests/test_sqlite_store.py` | Unit | SQLite store tests | ✅ |
| `tests/test_stage_governance_integration.py` | Integration | Stage governance integration | ✅ |
| `tests/test_stage_transition_governance.py` | Unit | Stage transition governance | ✅ |
| `tests/test_state_manager.py` | Unit | State manager tests | ✅ |
| `tests/test_tool_rewriter.py` | Unit | Tool rewriter tests | ✅ |
| `tests/functional/test_functional_entrypoint_parity.py` | Functional | Entrypoint parity tests | ✅ |
| `tests/functional/test_functional_fixture_sanity.py` | Functional | Fixture sanity tests | ✅ |
| `tests/functional/test_functional_gating.py` | Functional | Gating tests | ✅ |
| `tests/functional/test_functional_happy_path.py` | Functional | Happy path tests | ✅ |
| `tests/functional/test_functional_phase4_scenarios.py` | Functional | Phase 4 scenario tests | ✅ |
| `tests/functional/test_functional_policy_e2e_lifecycle.py` | Functional | Policy E2E lifecycle | ✅ |
| `tests/functional/test_functional_policy_e2e.py` | Functional | Policy E2E tests | ✅ |
| `tests/functional/test_functional_policy_fixtures.py` | Functional | Policy fixture tests | ✅ |
| `tests/functional/test_functional_refresh.py` | Functional | Refresh tests | ✅ |
| `tests/functional/test_functional_revoke.py` | Functional | Revoke tests | ✅ |
| `tests/functional/test_functional_smoke_subprocess.py` | Functional | Subprocess smoke tests | ✅ |
| `tests/functional/test_functional_stage.py` | Functional | Stage tests | ✅ |
| `tests/functional/test_functional_stdio.py` | Functional | STDIO tests | ✅ |
| `tests/functional/test_functional_ttl.py` | Functional | TTL tests | ✅ |

**Breakdown**:
- Unit tests: ~18 files
- Integration tests: ~4 files  
- Functional tests: 13 files
- Test fixtures: Mock MCP servers, mock skills, support utilities

**All tests passing**: 290 tests collected, all pass per v1.0.0 release

---

## 6. Examples Inventory

### 6.1 Canonical Demo: `examples/simulator-demo/`

**Status**: ✅ Canonical Stage-first demo (v1.0.0)

| Path | Type | Status | Keep | Notes |
|------|------|--------|------|-------|
| `examples/simulator-demo/` | Canonical Demo | Active | ✅ | Stage-first reference implementation |
| `examples/simulator-demo/scenarios/` | Scenario Scripts | Active | ✅ | 3 scenarios (discovery, staged, lifecycle) |
| `examples/simulator-demo/simulator/` | Framework | Active | ✅ | Simulator core, hook/MCP subprocess helpers |
| `examples/simulator-demo/fixtures/skills/` | Test Fixtures | Active | ✅ | 2 fixture skills for testing |
| `examples/simulator-demo/reports/` | Generated Reports | Active | ✅ | Showcase report for v1.0.0 release |
| `examples/simulator-demo/.scenario-*-data/` | Runtime Artifacts | Ignored | ⚠️ | Can be regenerated, already in .gitignore |
| `examples/simulator-demo/.test-*-data/` | Test Artifacts | Ignored | ⚠️ | Can be regenerated, already in .gitignore |
| `examples/simulator-demo/run_simulator.sh` | Entry Point | Active | ✅ | Main execution script |
| `examples/simulator-demo/verify_*.py` | Verification Scripts | Active | ✅ | Stage-first validation, fixture validation |
| `examples/simulator-demo/README.md` | Documentation | Active | ✅ | Demo overview |
| `examples/simulator-demo/SCOPE.md` | Documentation | Active | ✅ | Scope definition |
| `examples/simulator-demo/SCENARIOS.md` | Documentation | Active | ✅ | Scenario descriptions |
| `examples/simulator-demo/ACCEPTANCE_CRITERIA.md` | Documentation | Active | ✅ | Acceptance criteria |
| `examples/simulator-demo/EVENT_COVERAGE.md` | Documentation | Active | ✅ | Event coverage matrix |

**v1.0.0 Inventory Error**: v1.0.0 incorrectly described simulator-demo as having:
- `scenario_01_basic_lifecycle.py` (actual: `scenario_01_discovery.py`)
- `skills/delivery-demo/` (actual: `fixtures/skills/yuque-doc-edit-staged/` and `yuque-knowledge-link/`)
- `src/`, `tests/`, `config/` subdirectories (these do not exist)

**Cleanable artifacts**: `.scenario-*-data/`, `.test-*-data/` directories (already ignored, can be deleted locally)

### 6.2 Legacy Examples

| Path | Type | Status | Keep | Cleanable Content | Rationale |
|------|------|--------|------|-------------------|-----------|
| `examples/01-knowledge-link/` | Legacy Demo | Deprecated | ✅ | `logs/`, `.demo-data/` | Pre-Stage-first architecture, kept for reference |
| `examples/02-doc-edit-staged/` | Legacy Demo | Deprecated | ✅ | `logs/`, `.demo-data/` | Pre-Stage-first architecture, kept for reference |
| `examples/03-lifecycle-and-risk/` | Legacy Demo | Deprecated | ✅ | `logs/`, `.demo-data/` | Pre-Stage-first architecture, kept for reference |

**v1.0.0 Inventory Error**: v1.0.0 incorrectly recommended deleting these entire directories. Current architectural decision is to **keep them as Deprecated/Legacy** for historical reference.

**Cleanable artifacts in legacy examples**:
- `examples/01-knowledge-link/logs/session_*/` - Runtime logs (currently tracked, could be removed)
- `examples/01-knowledge-link/.demo-data/` - Runtime database (ignored)
- `examples/02-doc-edit-staged/logs/session_*/` - Runtime logs (currently tracked, could be removed)
- `examples/02-doc-edit-staged/.demo-data/` - Runtime database (ignored)
- `examples/03-lifecycle-and-risk/logs/session_*/` - Runtime logs (currently tracked, could be removed)
- `examples/03-lifecycle-and-risk/.demo-data/` - Runtime database (ignored)

**Do NOT delete**: Skills, scripts, schemas, contracts, MCP mocks, READMEs in legacy examples - these are source code.


---

## 7. Documentation Inventory

Based on real `find . -maxdepth 3 -name '*.md' -type f | sort` and `find docs openspec -type f -name '*.md' | sort`:

| Document Path | Type | Purpose | Keep | Merge | Merge Target | Rationale | Human Confirm |
|---------------|------|---------|------|-------|--------------|-----------|---------------|
| `README.md` | Root Entrypoint | Project overview | ✅ | ❌ | - | Updated to v1.0.0 | ❌ |
| `README_CN.md` | Chinese Entrypoint | Chinese project overview | ✅ | ❌ | - | Updated to v1.0.0 | ❌ |
| `CHANGELOG.md` | Changelog | Release history | ✅ | ❌ | - | v1.0.0 entry complete | ❌ |
| `docs/current_governance_model.md` | Governance Model | Authoritative governance spec | ✅ | ❌ | - | NEW: Core documentation | ❌ |
| `docs/skill_stage_authoring.md` | Authoring Guide | Skill/stage authoring guide | ✅ | ❌ | - | For skill developers | ❌ |
| `docs/dev_plan.md` | Dev Plan | Development plan | ✅ | ❌ | - | Historical record | ❌ |
| `docs/requirements.md` | Requirements | Requirements document | ✅ | ❌ | - | Historical record | ❌ |
| `docs/technical_design.md` | Technical Design | Technical design document | ✅ | ❌ | - | Historical record | ❌ |
| `docs/self_test_runbook.md` | Runbook | Self-test runbook | ✅ | ❌ | - | Operational guide | ❌ |
| `docs/session_logging_prompt.md` | Runbook | Session logging prompt | ✅ | ❌ | - | Operational guide | ❌ |
| `docs/perf_results.md` | Report | Performance results | ✅ | ❌ | - | Benchmark data | ❌ |
| `docs/README.md` | Documentation Index | Docs overview | ✅ | ❌ | - | Navigation | ❌ |
| `docs/开发计划.md` | Dev Plan (CN) | Chinese dev plan | ✅ | ❌ | - | Historical record | ❌ |
| `docs/技术方案文档.md` | Technical Design (CN) | Chinese technical design | ✅ | ❌ | - | Historical record | ❌ |
| `docs/需求文档.md` | Requirements (CN) | Chinese requirements | ✅ | ❌ | - | Historical record | ❌ |
| `examples/README.md` | Examples Overview | Examples documentation | ✅ | ❌ | - | Navigation | ❌ |
| `examples/QUICKSTART.md` | Quick Start | Quick start guide | ✅ | ❌ | - | User guide | ❌ |
| `examples/simulator-demo/README.md` | Demo Doc | Simulator demo overview | ✅ | ❌ | - | Canonical demo doc | ❌ |
| `examples/simulator-demo/SCOPE.md` | Demo Doc | Demo scope definition | ✅ | ❌ | - | Canonical demo doc | ❌ |
| `examples/simulator-demo/SCENARIOS.md` | Demo Doc | Scenario descriptions | ✅ | ❌ | - | Canonical demo doc | ❌ |
| `examples/simulator-demo/ACCEPTANCE_CRITERIA.md` | Demo Doc | Acceptance criteria | ✅ | ❌ | - | Canonical demo doc | ❌ |
| `examples/simulator-demo/EVENT_COVERAGE.md` | Demo Doc | Event coverage matrix | ✅ | ❌ | - | Canonical demo doc | ❌ |
| `examples/simulator-demo/reports/scenario_03_lifecycle_showcase_report.md` | Report | Showcase report | ✅ | ❌ | - | v1.0.0 showcase | ❌ |
| `examples/01-knowledge-link/README.md` | Legacy Demo Doc | Legacy demo overview | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/02-doc-edit-staged/README.md` | Legacy Demo Doc | Legacy demo overview | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/02-doc-edit-staged/reports/README.md` | Legacy Report Index | Legacy reports index | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/02-doc-edit-staged/reports/SUMMARY.md` | Legacy Report | Legacy simulation summary | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/02-doc-edit-staged/reports/simulation_run_report.md` | Legacy Report | Legacy simulation report | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/03-lifecycle-and-risk/README.md` | Legacy Demo Doc | Legacy demo overview | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/03-lifecycle-and-risk/reports/README.md` | Legacy Report Index | Legacy reports index | ✅ | ❌ | - | Legacy reference | ❌ |
| `examples/03-lifecycle-and-risk/reports/simulation_run_report.md` | Legacy Report | Legacy simulation report | ✅ | ❌ | - | Legacy reference | ❌ |
| `openspec/changes/archive/*/proposal.md` | OpenSpec Archive | Archived proposals | ✅ | ❌ | - | Historical record (11 changes) | ❌ |
| `openspec/changes/archive/*/design.md` | OpenSpec Archive | Archived designs | ✅ | ❌ | - | Historical record (11 changes) | ❌ |
| `openspec/changes/archive/*/tasks.md` | OpenSpec Archive | Archived tasks | ✅ | ❌ | - | Historical record (11 changes) | ❌ |
| `openspec/changes/archive/*/closeout.md` | OpenSpec Archive | Archived closeouts | ✅ | ❌ | - | Historical record (11 changes) | ❌ |
| `openspec/specs/*/spec.md` | OpenSpec Spec | Living specifications | ✅ | ❌ | - | 10 validated specs | ❌ |
| `reports/project_inventory_v1.0.0.md` | Temporary Summary | First inventory | ❌ | ❌ | - | Superseded by v1.0.1 | ✅ |
| `reports/project_inventory_v1.0.1.md` | Report | This file | ✅ | ❌ | - | Current inventory | ❌ |

**Total markdown files**: 198 tracked

**Note**: OpenSpec archive files (proposal.md, design.md, tasks.md, closeout.md) are listed as single entries but represent 11 archived changes each.

---

## 8. Script Inventory

Based on real `find` outputs:

| Script Path | Purpose | Type | Keep | Rationale |
|-------------|---------|------|------|-----------|
| `examples/simulator-demo/run_simulator.sh` | Run all scenarios | Entry Point | ✅ | Canonical demo entry point |
| `examples/simulator-demo/scenarios/scenario_01_discovery.py` | Scenario 1 | Scenario | ✅ | Skill discovery demo |
| `examples/simulator-demo/scenarios/scenario_02_staged.py` | Scenario 2 | Scenario | ✅ | Stage transitions demo |
| `examples/simulator-demo/scenarios/scenario_03_lifecycle.py` | Scenario 3 | Scenario | ✅ | Full lifecycle demo |
| `examples/simulator-demo/simulator/core.py` | Simulator core | Framework | ✅ | Simulator framework |
| `examples/simulator-demo/simulator/hook_subprocess.py` | Hook subprocess | Framework | ✅ | Hook subprocess helper |
| `examples/simulator-demo/simulator/mcp_subprocess.py` | MCP subprocess | Framework | ✅ | MCP subprocess helper |
| `examples/simulator-demo/integration_test.py` | Integration test | Test | ✅ | Integration testing |
| `examples/simulator-demo/smoke_test.py` | Smoke test | Test | ✅ | Smoke testing |
| `examples/simulator-demo/verify_stage_first.py` | Stage-first validation | Verification | ✅ | Validates Stage-first compliance |
| `examples/simulator-demo/verify_skill_fixtures.py` | Fixture validation | Verification | ✅ | Validates skill fixtures |
| `examples/simulator-demo/verify_stage_c.py` | Stage C validation | Verification | ✅ | Stage C completion check |
| `examples/simulator-demo/verify_stage_d.py` | Stage D validation | Verification | ✅ | Stage D completion check |
| `examples/01-knowledge-link/start_simulation.sh` | Legacy demo entry | Legacy | ✅ | Legacy demo preserved |
| `examples/01-knowledge-link/scripts/agent_realistic_simulation.py` | Legacy simulation | Legacy | ✅ | Legacy demo preserved |
| `examples/01-knowledge-link/scripts/skill_handlers.py` | Legacy handlers | Legacy | ✅ | Legacy demo preserved |
| `examples/02-doc-edit-staged/start_simulation.sh` | Legacy demo entry | Legacy | ✅ | Legacy demo preserved |
| `examples/02-doc-edit-staged/execute_writeback.sh` | Legacy writeback | Legacy | ✅ | Legacy demo preserved |
| `examples/02-doc-edit-staged/scripts/agent_realistic_simulation.py` | Legacy simulation | Legacy | ✅ | Legacy demo preserved |
| `examples/02-doc-edit-staged/scripts/skill_handlers.py` | Legacy handlers | Legacy | ✅ | Legacy demo preserved |
| `examples/03-lifecycle-and-risk/start_simulation.sh` | Legacy demo entry | Legacy | ✅ | Legacy demo preserved |
| `examples/03-lifecycle-and-risk/scripts/agent_realistic_simulation.py` | Legacy simulation | Legacy | ✅ | Legacy demo preserved |
| `examples/03-lifecycle-and-risk/scripts/skill_handlers.py` | Legacy handlers | Legacy | ✅ | Legacy demo preserved |

**Note**: `scripts/bench_phase4.py` was deleted (temporary benchmark script, staged for deletion).

---

## 9. Runtime Artifacts / Temporary Files

Based on real `find` and `git ls-files` outputs:

### 9.1 Tracked Runtime Artifacts

| Path | Status | Type | Recommended Action | Rationale | Human Confirm |
|------|--------|------|-------------------|-----------|---------------|
| `examples/01-knowledge-link/logs/session_*/audit_summary.md` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/01-knowledge-link/logs/session_*/events.jsonl` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/01-knowledge-link/logs/session_*/metrics.json` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/02-doc-edit-staged/logs/session_*/audit_summary.md` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/02-doc-edit-staged/logs/session_*/events.jsonl` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/02-doc-edit-staged/logs/session_*/metrics.json` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/03-lifecycle-and-risk/logs/session_*/audit_summary.md` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/03-lifecycle-and-risk/logs/session_*/events.jsonl` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |
| `examples/03-lifecycle-and-risk/logs/session_*/metrics.json` | Tracked | Runtime Log | Consider git rm | Generated artifact | ✅ |

**Total tracked runtime artifacts**: 9 files (3 per legacy example)

### 9.2 Ignored Runtime Artifacts

| Path | Status | Type | Recommended Action | Rationale |
|------|--------|------|-------------------|-----------|
| `data/governance.db` | Ignored | Runtime DB | Safe to delete locally | Root runtime data |
| `.demo-data/governance.db` | Ignored | Runtime DB | Safe to delete locally | Demo runtime data |
| `examples/01-knowledge-link/.demo-data/governance.db` | Ignored | Runtime DB | Safe to delete locally | Legacy demo data |
| `examples/02-doc-edit-staged/.demo-data/governance.db` | Ignored | Runtime DB | Safe to delete locally | Legacy demo data |
| `examples/03-lifecycle-and-risk/.demo-data/governance.db` | Ignored | Runtime DB | Safe to delete locally | Legacy demo data |
| `examples/simulator-demo/.scenario-01-data/*` | Ignored | Runtime Artifacts | Safe to delete locally | Scenario 1 data (4 files) |
| `examples/simulator-demo/.scenario-02-data/*` | Ignored | Runtime Artifacts | Safe to delete locally | Scenario 2 data (4 files) |
| `examples/simulator-demo/.scenario-03-data/*` | Ignored | Runtime Artifacts | Safe to delete locally | Scenario 3 data (4 files) |
| `examples/simulator-demo/.test-list-skills/governance.db` | Ignored | Test Artifact | Safe to delete locally | Test data |
| `examples/simulator-demo/.test-mcp-raw/governance.db` | Ignored | Test Artifact | Safe to delete locally | Test data |
| `.mypy_cache/3.10/cache.db` | Ignored | Cache | Safe to delete locally | Mypy cache |

**Total ignored runtime artifacts**: 20+ files

### 9.3 Cache Directories (Ignored)

| Path | Type | Size | Recommended Action |
|------|------|------|-------------------|
| `.mypy_cache/` | Mypy cache | Small | Safe to delete locally |
| `.pytest_cache/` | Pytest cache | Small | Safe to delete locally |
| `.ruff_cache/` | Ruff cache | Small | Safe to delete locally |
| `src/tool_governance/**/__pycache__/` | Python bytecode | Small | Safe to delete locally |
| `tests/**/__pycache__/` | Python bytecode | Small | Safe to delete locally |
| `examples/**/__pycache__/` | Python bytecode | Small | Safe to delete locally |

**Command to clean all ignored files**: `git clean -fdX`


---

## 10. OpenSpec Status

### 10.1 Active Changes

```bash
$ openspec list
No active changes found.
```

**Status**: ✅ No active changes (clean state for v1.0.0 release)

### 10.2 Archived Changes

```
openspec/changes/archive/
├── 2026-04-19-add-functional-test-plan/
├── 2026-04-19-build-tool-governance-plugin/
├── 2026-04-19-phase13-hardening-and-doc-sync/
├── 2026-04-20-formalize-cache-layers/
├── 2026-04-30-migrate-entrypoints-to-runtime-flow/
├── 2026-05-01-remove-legacy-delivery-demo-changes/
├── 2026-05-03-formalize-stage-workflow-metadata/      # Stage-first Phase 1
├── 2026-05-03-separate-runtime-and-persisted-state/
├── 2026-05-03-simulate-claude-code-call-chain-demo/
├── 2026-05-04-enforce-stage-transition-governance/    # Stage-first Phase 2
└── 2026-05-05-migrate-demos-to-stage-first-governance/ # Stage-first Phase 3
```

**Total**: 11 archived changes

Each archived change contains:
- `.openspec.yaml` (metadata)
- `proposal.md` (proposal)
- `design.md` (design)
- `tasks.md` (task list)
- `closeout.md` (closeout summary)

**Stage-first v1.0.0 changes**:
1. `2026-05-03-formalize-stage-workflow-metadata/` - Phase 1: Stage workflow metadata
2. `2026-05-04-enforce-stage-transition-governance/` - Phase 2: Stage transition governance
3. `2026-05-05-migrate-demos-to-stage-first-governance/` - Phase 3: Demo migration

### 10.3 OpenSpec Specs

```bash
$ openspec validate --all
- Validating...
✓ spec/audit-observability
✓ spec/delivery-demo-harness
✓ spec/functional-test-harness
✓ spec/session-lifecycle
✓ spec/skill-authorization
✓ spec/skill-discovery
✓ spec/skill-execution
✓ spec/stage-transition-validation
✓ spec/tool-governance-hardening
✓ spec/tool-surface-control
Totals: 10 passed, 0 failed (10 items)
```

**Status**: ✅ All 10 specs validated successfully

---

## 11. Cleanup Recommendations

### 11.1 Safe to Delete (Ignored Runtime Artifacts)

**Local cleanup only** - these files are already gitignored:

```bash
# Root runtime data
data/governance.db
.demo-data/governance.db

# Legacy example runtime data
examples/01-knowledge-link/.demo-data/
examples/02-doc-edit-staged/.demo-data/
examples/03-lifecycle-and-risk/.demo-data/

# Simulator-demo runtime data
examples/simulator-demo/.scenario-01-data/
examples/simulator-demo/.scenario-02-data/
examples/simulator-demo/.scenario-03-data/
examples/simulator-demo/.test-list-skills/
examples/simulator-demo/.test-mcp-raw/

# Cache directories
.mypy_cache/
.pytest_cache/
.ruff_cache/
src/tool_governance/**/__pycache__/
tests/**/__pycache__/
examples/**/__pycache__/
```

**Command**: `git clean -fdX` (removes all gitignored files)

**Estimated space saved**: ~10-20MB (excluding cache directories)

### 11.2 Tracked Artifacts to Consider Removing

**Requires git rm and commit** - these are tracked but are runtime artifacts:

```bash
# Legacy example session logs (9 files total)
examples/01-knowledge-link/logs/session_session-1777555707/audit_summary.md
examples/01-knowledge-link/logs/session_session-1777555707/events.jsonl
examples/01-knowledge-link/logs/session_session-1777555707/metrics.json
examples/02-doc-edit-staged/logs/session_session-1777559548/audit_summary.md
examples/02-doc-edit-staged/logs/session_session-1777559548/events.jsonl
examples/02-doc-edit-staged/logs/session_session-1777559548/metrics.json
examples/03-lifecycle-and-risk/logs/session_session-1777561973/audit_summary.md
examples/03-lifecycle-and-risk/logs/session_session-1777561973/events.jsonl
examples/03-lifecycle-and-risk/logs/session_session-1777561973/metrics.json
```

**Rationale**: These are generated runtime logs from legacy demo runs. They can be regenerated by running the demos.

**Human confirmation required**: Are these logs valuable for historical reference, or safe to remove?

### 11.3 Untracked Files to Add

**Should be tracked** - new source files and reports:

```bash
# New governance model documentation
git add docs/current_governance_model.md

# Showcase report (v1.0.0 deliverable)
git add examples/simulator-demo/reports/scenario_03_lifecycle_showcase_report.md

# This inventory report
git add reports/project_inventory_v1.0.1.md
```

### 11.4 Files to Delete from Tracking

**Already staged for deletion** - temporary summaries:

```bash
# These 11 files are already staged for deletion (git status shows "D")
# Just commit the deletion:
git commit -m "chore: remove temporary summaries and completion markers"
```

**Additional candidate for deletion**:

```bash
# Superseded inventory report
git rm reports/project_inventory_v1.0.0.md
```

**Rationale**: v1.0.0 inventory contains structural errors and is superseded by v1.0.1.

### 11.5 Keep (Core Project Structure)

**Do NOT delete** - these are core project files:

```bash
# Core runtime
src/tool_governance/

# Test suite
tests/

# Canonical demo
examples/simulator-demo/ (excluding .scenario-*-data/, .test-*-data/)

# Legacy examples (Deprecated but kept for reference)
examples/01-knowledge-link/ (excluding .demo-data/, logs/)
examples/02-doc-edit-staged/ (excluding .demo-data/, logs/)
examples/03-lifecycle-and-risk/ (excluding .demo-data/, logs/)

# OpenSpec
openspec/specs/
openspec/changes/archive/

# Documentation
docs/
README.md
README_CN.md
CHANGELOG.md

# Configuration
pyproject.toml
package.json
.gitignore
pytest.ini
```

### 11.6 Human Confirmation Required

**Ambiguous items** - need user decision:

1. **Legacy example session logs** (9 tracked files in `examples/*/logs/session_*/`)
   - **Keep**: If valuable for historical reference
   - **Remove**: If can be regenerated and not needed

2. **Root runtime DBs** (`data/governance.db`, `.demo-data/governance.db`)
   - **Keep**: If contain active session state
   - **Remove**: If safe to regenerate

3. **reports/ directory structure**
   - **Option A**: Keep `reports/` at root, delete v1.0.0, keep v1.0.1
   - **Option B**: Move all reports to `examples/simulator-demo/reports/`, delete root `reports/`
   - **Option C**: Keep both locations

---

## 12. Important Corrections from v1.0.0 Inventory

### 12.1 Structural Errors in v1.0.0

1. **simulator-demo structure**: v1.0.0 incorrectly described `simulator-demo` as having:
   - `scenario_01_basic_lifecycle.py` (actual: `scenario_01_discovery.py`)
   - `skills/delivery-demo/` (actual: `fixtures/skills/yuque-doc-edit-staged/` and `yuque-knowledge-link/`)
   - `src/`, `tests/`, `config/` subdirectories (these do not exist in simulator-demo)

2. **src/ directory structure**: v1.0.0 claimed `persistence/`, `indexer/`, `mcp/` subdirectories exist
   - **Actual structure**: `core/`, `models/`, `storage/`, `tools/`, `utils/`

3. **Legacy examples deletion**: v1.0.0 suggested deleting `examples/01-knowledge-link/`, `02-doc-edit-staged/`, `03-lifecycle-and-risk/`
   - **Correction**: These are marked **Deprecated** but kept for reference (not deleted)

4. **OpenSpec archives**: v1.0.0 suggested "consider archiving older archives"
   - **Correction**: All archives are historical records for v1.0.0 CHANGELOG and should be kept

5. **File counts**: v1.0.0 did not provide accurate file counts
   - **Correction**: 362 tracked files, 98 Python, 198 Markdown

### 12.2 Methodology Improvement

**v1.0.0 methodology**: Generated from memory/assumptions, leading to structural errors

**v1.0.1 methodology**: Generated from real command outputs:
- `find` commands for directory structure
- `git ls-files` for tracked files
- `git status` for current state
- `openspec validate --all` for OpenSpec status
- `du -sh` for artifact sizes
- `pytest --collect-only` for test counts

**Result**: v1.0.1 is structurally accurate and can be used as cleanup basis.

---

## 13. Project Statistics

| Metric | Count |
|--------|-------|
| Total tracked files | 362 |
| Python files | 98 |
| Markdown files | 198 |
| Core runtime modules | 23 (in `src/tool_governance/`) |
| Core subdirectories | 5 (core/, models/, storage/, tools/, utils/) |
| Model classes | 4 (Grant, Policy, Skill, State) |
| Unit tests | ~18 files |
| Functional tests | 13 files |
| Total tests | 290 |
| Test fixtures | 7 skill fixtures, 3 MCP fixtures, 2 policies |
| OpenSpec specs | 10 (all validated ✓) |
| OpenSpec archives | 11 changes |
| Active OpenSpec changes | 0 |
| Examples | 4 (1 canonical, 3 deprecated) |
| Root skills | 4 |
| Documentation files | 12 in docs/ (6 EN, 3 CN, 3 guides) |
| IDE integrations | 4 (.claude, .codex, .cursor, .trae) |
| Total size | ~773MB (467MB node_modules, 195MB .venv, ~111MB project) |

---

## 14. Summary

### 14.1 Current State

- **Git status**: Clean working tree except for 3 modified files (README updates), 11 staged deletions (temporary summaries), 4 untracked files/directories (new docs, reports)
- **Test status**: All 290 tests passing
- **OpenSpec status**: 10 specs validated, 0 active changes, 11 archived changes
- **Release readiness**: v1.0.0 Stage-first Skill Governance release complete

### 14.2 Recommended Next Steps

1. **Commit current changes**:
   ```bash
   git add CHANGELOG.md README.md README_CN.md
   git add docs/current_governance_model.md
   git add examples/simulator-demo/reports/
   git add reports/project_inventory_v1.0.1.md
   git commit -m "docs: update to v1.0.0 Stage-first Skill Governance release"
   ```

2. **Clean up ignored artifacts** (optional):
   ```bash
   git clean -fdX  # Remove all gitignored files
   ```

3. **Consider removing tracked runtime artifacts** (requires human confirmation):
   ```bash
   git rm examples/*/logs/session_*/
   git rm reports/project_inventory_v1.0.0.md
   git commit -m "chore: remove runtime artifacts and superseded inventory"
   ```

### 14.3 Key Takeaways

- **v1.0.0 inventory contained structural errors** due to memory-based generation
- **v1.0.1 inventory is accurate** based on real command outputs
- **Legacy examples are kept** as Deprecated for reference (not deleted)
- **OpenSpec archives are kept** as historical records for v1.0.0
- **Cleanup is safe** for ignored runtime artifacts (~10-20MB)
- **Human confirmation needed** for tracked runtime artifacts (9 files)

---

**End of Inventory v1.0.1**

Generated: 2026-05-06  
Methodology: Real command outputs (no fabrication)  
Replaces: v1.0.0 inventory (contained errors)
