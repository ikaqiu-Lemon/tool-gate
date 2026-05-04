# delivery-demo-harness Specification

## Purpose
TBD - created by archiving change add-delivery-demo-workspaces. Update Purpose after archive.
## Requirements
### Requirement: Independent Demo Workspaces Under `examples/`

The delivery demo harness SHALL organize showcase artifacts as **independent demo workspaces** under `examples/`, with one directory per demo. Each workspace MUST be runnable by `cd` into the directory and starting Claude Code from there without relying on global environment variables beyond what the plugin itself defines.

#### Scenario: Three workspaces exist side-by-side

- **WHEN** a reviewer opens `examples/`
- **THEN** three sibling directories are present: `01-knowledge-link/`, `02-doc-edit-staged/`, `03-lifecycle-and-risk/`
- **AND** no shared `skills/`, `mcp/`, or `config/` directory exists at `examples/` top level

#### Scenario: Workspace self-contained startup

- **WHEN** a reviewer runs `cd examples/01-knowledge-link/ && claude --plugin-dir ../../ --mcp-config ./.mcp.json`
- **THEN** the Claude Code session starts with tool-gate loaded and the workspace's own mock MCP servers registered
- **AND** no additional environment variable beyond the plugin's own (`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`) is required

### Requirement: Minimum Asset Set Per Workspace

Each demo workspace MUST contain at minimum: a `README.md` (per unified template), a `skills/` directory (only the skills used by this demo), a `mcp/` directory (only the mock stdio MCP servers used by this demo), a `config/demo_policy.yaml`, a `.mcp.json`, a `contracts/` directory (markdown contract tables), and a `schemas/` directory (JSON Schema files).

#### Scenario: Workspace asset completeness

- **WHEN** the harness inspects any `examples/0X-*/` directory
- **THEN** all seven asset classes (README, skills/, mcp/, config/, .mcp.json, contracts/, schemas/) are present
- **AND** `skills/` contains only SKILL.md files used by this demo's main or episodic flow
- **AND** `mcp/` contains only the mock stdio server files referenced by this demo's `.mcp.json`

#### Scenario: No cross-workspace dependency

- **WHEN** any single workspace is removed from the filesystem
- **THEN** the other two workspaces remain fully runnable
- **AND** their `README.md` files contain no path reference pointing into the removed workspace

### Requirement: `.mcp.json` Uses Relative Paths Only

Every workspace's `.mcp.json` MUST reference mock MCP server scripts via relative paths (e.g. `./mcp/mock_yuque_stdio.py`). Absolute paths, `${CLAUDE_PLUGIN_ROOT}`-derived paths, or paths into other workspaces are prohibited.

#### Scenario: Relative path enforcement

- **WHEN** any `examples/0X-*/.mcp.json` is parsed
- **THEN** every `args` entry containing a filesystem path starts with `./` or `../` and stays within the same workspace
- **AND** no entry uses `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PROJECT_DIR}`, or an absolute filesystem path

### Requirement: Three-Column Operation Steps With Absolute Ascending Timestamps

Every workspace `README.md` MUST present its operation steps in a single table with exactly four columns — `时间戳 / 操作者输入 / 模型预期动作 / 系统侧事件` — where the timestamp column uses ISO 8601 absolute format with timezone offset (`YYYY-MM-DDTHH:MM:SS+08:00`) and is strictly monotonically increasing within the table.

#### Scenario: Three-column table present

- **WHEN** a reviewer opens any `examples/0X-*/README.md`
- **THEN** `§3 操作步骤` contains a markdown table whose header row is exactly `时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件`

#### Scenario: Ascending distinct timestamps

- **WHEN** the timestamp column of the operation-step table is parsed
- **THEN** every row has a distinct timestamp in ISO 8601 format with `+08:00` offset
- **AND** each row's timestamp is strictly greater than the previous row's

### Requirement: Two Coverage Matrices In Root `examples/README.md`

`examples/README.md` MUST contain both a capability coverage matrix (rows = 6 capability spec names; columns = 01 / 02 / 03) and a function/interface coverage matrix (rows = 15 items spanning 8 MCP meta-tools + 4 hook types + `error_bucket` / `TTL/revoke` / `funnel/trace`; columns = 01 / 02 / 03). Each filled cell MUST be traceable to a concrete step in the referenced workspace's `README.md`.

#### Scenario: Capability matrix row set

- **WHEN** a reviewer inspects the capability coverage matrix
- **THEN** its row labels are exactly `skill-discovery`, `skill-authorization`, `skill-execution`, `session-lifecycle`, `tool-surface-control`, `audit-observability`

#### Scenario: Function/interface matrix row set

- **WHEN** a reviewer inspects the function/interface coverage matrix
- **THEN** its row labels include all 8 MCP meta-tools (`list_skills`, `read_skill`, `enable_skill`, `disable_skill`, `grant_status`, `run_skill_action`, `change_stage`, `refresh_skills`), all 4 hook types (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`), and the three diagnostic signals (`error_bucket`, `TTL / revoke`, `funnel / trace`)

#### Scenario: Filled cell traceability

- **WHEN** any cell in either matrix is marked `●`
- **THEN** the corresponding workspace's `README.md` contains at least one operation-step row whose "系统侧事件" column references the matching capability, tool, hook, or signal by name

### Requirement: Example 03 Theme Locked On Lifecycle And Risk Escalation

Example 03's main operation-step table MUST cover only TTL expiry, revoke, disable, high-risk `approval_required` denial, and audit-order closure. `refresh_skills` MUST NOT appear in Example 03's main three-column table; it MAY appear only in an explicitly labeled appendix section as an auxiliary touch-point.

#### Scenario: Main flow excludes refresh_skills

- **WHEN** the main operation-step table of `examples/03-lifecycle-and-risk/README.md` is parsed
- **THEN** no row's "模型预期动作" column contains the string `refresh_skills`

#### Scenario: Refresh_skills main showcase belongs to Example 01

- **WHEN** a reviewer searches across `examples/0X-*/README.md` for the primary `refresh_skills` demonstration
- **THEN** the main demonstration flow for `refresh_skills` is located inside `examples/01-knowledge-link/README.md` (either in the main table or an explicit appendix section)

### Requirement: Per-Mock-Tool Contract Table

Every mock MCP tool introduced by any workspace MUST have a contract entry inside that workspace's `contracts/*.md`. Each entry MUST include at minimum the following six fields: tool name (as header), owning MCP server, role classification (`主业务工具` / `混杂变量工具` / `高风险工具`), input field list, output field list, example return (JSON block with 2–3 hardcoded samples), role within this specific workspace, and a link to the corresponding `schemas/<tool>.schema.json`.

#### Scenario: Contract completeness

- **WHEN** any mock MCP tool is declared in a workspace's `.mcp.json` or referenced by any step of the workspace README
- **THEN** a contract section with that tool's name exists in `examples/0X-*/contracts/*.md`
- **AND** all six required fields plus the schema link are filled in

#### Scenario: Contract-schema cross-reference

- **WHEN** any contract entry lists a schema link
- **THEN** the referenced `schemas/<tool>.schema.json` file exists in the same workspace

### Requirement: JSON Schema Per Mock Tool With Input And Output Subschemas

For every mock MCP tool with a contract entry, the workspace SHALL contain a `schemas/<tool>.schema.json` file that validates both input arguments and output payloads. The schema file MUST be syntactically valid JSON and conformant to JSON Schema Draft 2020-12 or later.

#### Scenario: Schema file present and valid JSON

- **WHEN** any `examples/0X-*/schemas/*.schema.json` is loaded
- **THEN** it parses as valid JSON
- **AND** it declares `$schema` pointing at JSON Schema Draft 2020-12 or later

#### Scenario: Input and output subschemas both defined

- **WHEN** any schema file is inspected
- **THEN** it contains distinct `input` and `output` subschemas (or equivalent `properties.input` / `properties.output` keys)

### Requirement: `mock_shell_stdio.py` Role Disclaimer

Wherever `mock_shell_stdio.py` appears — inside `contracts/shell_tools_contract.md`, inside the Python file's module docstring, and inside the workspace `README.md`'s "Mock 工具契约速览" section — a disclaimer MUST state verbatim that it is a **混杂变量工具**, used only to create a realistic mixed-tool environment for demonstrating tool-gate's interception capability, and does NOT indicate that this project supports arbitrary shell execution.

#### Scenario: Contract disclaimer present

- **WHEN** `contracts/shell_tools_contract.md` is opened
- **THEN** its first section (before any tool entry) contains the disclaimer stating "**混杂变量工具**" and "**不代表**本项目支持任意 shell 执行"

#### Scenario: Python module disclaimer present (Phase B)

- **WHEN** `mcp/mock_shell_stdio.py` exists (Phase B output)
- **THEN** its module-level docstring includes the same "混杂变量工具 … 不代表本项目支持任意 shell 执行" statement

### Requirement: `examples/README.md` Yuque Disclaimer At Top

`examples/README.md` MUST begin (immediately under the first heading, before any other content) with the verbatim paragraph: "本示例使用 Yuque 风格的 mock 工具仅作为稳定、可控的演示载体;项目本身并不绑定 Yuque 领域。"

#### Scenario: Disclaimer placement

- **WHEN** `examples/README.md` is opened
- **THEN** the first paragraph after the document's H1 heading is exactly the Yuque disclaimer text
- **AND** no other content precedes that paragraph

### Requirement: Phase A Skill SOP Depth — Skeleton Only

Phase A MUST deliver `SKILL.md` files whose YAML frontmatter is complete and parseable by `SkillIndexer`, while the markdown body (SOP) SHALL contain only structural skeleton: one H1 plus two-to-three H2 sections with 1–3 placeholder lines each, explicitly marked `<!-- Phase B 前补齐 -->`.

#### Scenario: Frontmatter fully populated

- **WHEN** any Phase A SKILL.md is parsed
- **THEN** its YAML frontmatter contains all required fields per `docs/technical_design.md`'s Skill metadata contract (`name`, `description`, `risk_level`, `version`, and either `allowed_tools` or `stages`)

#### Scenario: SOP skeleton markers

- **WHEN** any Phase A SKILL.md body is inspected
- **THEN** at least one `<!-- Phase B 前补齐 -->` marker is present under every H2 section

### Requirement: Phase Boundary — Phase A Produces No Python

Phase A MUST produce only documentation assets (markdown, YAML, JSON). No `*.py` files may be added to `examples/` during Phase A. Python mock MCP server implementations are a Phase B responsibility.

#### Scenario: Phase A Python prohibition

- **WHEN** Phase A is declared complete
- **THEN** `examples/**/*.py` yields zero matches

#### Scenario: Phase B Python lives under `mcp/`

- **WHEN** Phase B is declared complete
- **THEN** every `*.py` file under `examples/` resides inside a workspace's `mcp/` subdirectory
- **AND** no `*.py` file exists directly under `examples/` root or a workspace root

### Requirement: Phase B Mock Self-Validation Against Schema

When Phase B implements any `mock_*_stdio.py`, the server MUST self-validate its hardcoded sample payloads against the corresponding `schemas/<tool>.schema.json` on startup, and MUST refuse to start if any sample fails output-schema validation.

#### Scenario: Self-check on startup

- **WHEN** any Phase B `mock_*_stdio.py` is launched
- **THEN** it loads its paired schema file(s)
- **AND** validates every hardcoded output sample against the output subschema before accepting any `tools/call` request
- **AND** exits with a non-zero status if validation fails

### Requirement: Scope Guard — Core Code Untouched

This change SHALL NOT modify files under `src/tool_governance/`, `tests/functional/`, `skills/` (root-level project skills), `hooks/`, root-level `.mcp.json`, or `config/default_policy.yaml`. All changes MUST be confined to `examples/` plus optional additive links in root `README.md` / `README_CN.md`.

#### Scenario: Diff is scope-bound

- **WHEN** the full diff of this change is inspected
- **THEN** every modified or added file path falls under `examples/`, `openspec/changes/add-delivery-demo-workspaces/`, `docs/dev_plan.md` (append-only footer), or adds a single anchor link to `README.md` / `README_CN.md`
- **AND** no file under `src/tool_governance/`, `tests/`, `skills/`, `hooks/`, root `.mcp.json`, or `config/default_policy.yaml` is modified

### Requirement: Mixed-Tool Interception Demonstrated In Every Workspace

Each workspace MUST demonstrate tool-gate's hard-interception behavior by including at least one intentional "confounder" tool call attempt whose `系统侧事件` column records either a `PreToolUse` deny with `tool_not_available` or a `blocked_tools` denial. The confounder tool MUST be a real MCP tool registered via the workspace's `.mcp.json`, not a fictional name.

#### Scenario: Workspace 01 confounder

- **WHEN** Example 01's operation-step table is parsed
- **THEN** at least one row records a deny for `search_web`, `search_doc`, or `yuque_update_doc`
- **AND** the corresponding MCP is registered in `01-knowledge-link/.mcp.json`

#### Scenario: Workspace 02 confounder

- **WHEN** Example 02's operation-step table is parsed
- **THEN** at least one row records a `blocked_tools` denial for `run_command`
- **AND** `mock_shell_stdio` is registered in `02-doc-edit-staged/.mcp.json`

#### Scenario: Workspace 03 confounder

- **WHEN** Example 03's operation-step table is parsed
- **THEN** at least one row records either a high-risk `approval_required` denial for `yuque-bulk-delete` or a `blocked_tools` denial for `yuque_delete_doc`

### Requirement: Legacy Demo Changes MUST NOT Be Canonical Guidance

Legacy delivery-demo changes (archived `add-delivery-demo-workspaces` and active `harden-demo-workspace-onboarding`) MUST NOT be treated as canonical implementation guidance for demo workspaces. The canonical source of truth for demo workspace structure, behavior, and onboarding SHALL be `openspec/specs/delivery-demo-harness/` and the current `examples/` directory content.

#### Scenario: Reader discovers demo workspaces

- **WHEN** a new reader or agent explores the repository to understand demo workspaces
- **THEN** they SHALL be directed to `examples/README.md` and `examples/QUICKSTART.md` as the primary entry points
- **AND** they SHALL NOT be directed to `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` as default guidance

#### Scenario: Model searches for demo implementation guidance

- **WHEN** an AI model searches for "how to run demo workspaces" or "demo workspace structure"
- **THEN** the model SHALL find guidance in `examples/QUICKSTART.md` and `openspec/specs/delivery-demo-harness/spec.md`
- **AND** the model SHALL NOT treat legacy change artifacts as the primary source of truth

#### Scenario: Legacy changes referenced as historical context only

- **WHEN** legacy demo changes are referenced in documentation or commit messages
- **THEN** they MUST be explicitly labeled as "historical context only", "not canonical", or "superseded by current examples/"
- **AND** they SHALL NOT be presented as current implementation instructions

### Requirement: Repository Navigation MUST Point To Canonical Demo Path

Current repository navigation (README, QUICKSTART, agent guidance documents) MUST point readers and agents to `examples/` directory and `openspec/specs/delivery-demo-harness/` as the canonical demo source of truth. Navigation MUST NOT default to OpenSpec change artifacts for demo discovery.

#### Scenario: Root README demo navigation

- **WHEN** a reader opens the root `README.md` or `README_CN.md`
- **THEN** any demo-related links SHALL point to `examples/README.md` or `examples/QUICKSTART.md`
- **AND** no links SHALL point to `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` as primary demo entry points

#### Scenario: Agent guidance demo references

- **WHEN** agent guidance documents (`AGENTS.md`, `CLAUDE.md`, or similar) reference demo workspaces
- **THEN** they SHALL direct agents to `examples/` directory and `openspec/specs/delivery-demo-harness/`
- **AND** they SHALL NOT direct agents to legacy change artifacts as default demo guidance

#### Scenario: Examples directory as primary demo entry

- **WHEN** documentation describes how to explore demo workspaces
- **THEN** it SHALL state that `examples/README.md` and `examples/QUICKSTART.md` are the primary entry points
- **AND** it SHALL state that `openspec/specs/delivery-demo-harness/` defines the canonical requirements

### Requirement: Safe Deletion SHALL NOT Remove Current Requirements

Deleting legacy demo change directories SHALL NOT remove still-needed current requirements from main specs without replacement. Before deletion, all necessary demo workspace requirements MUST already exist in `openspec/specs/delivery-demo-harness/spec.md` or be explicitly documented as no longer needed.

#### Scenario: Pre-deletion requirement audit

- **WHEN** legacy demo changes are scheduled for deletion
- **THEN** a deletion impact report MUST be generated that lists all requirements from the legacy changes
- **AND** the report MUST confirm that each still-needed requirement already exists in the main spec or has been explicitly deprecated

#### Scenario: Main spec completeness after deletion

- **WHEN** legacy demo change directories are deleted
- **THEN** `openspec/specs/delivery-demo-harness/spec.md` MUST contain all current demo workspace requirements
- **AND** `openspec validate --all` MUST pass without errors

#### Scenario: Historical requirements explicitly marked

- **WHEN** a requirement from a legacy change is no longer needed
- **THEN** the deletion impact report MUST explicitly state why it is no longer needed
- **AND** the requirement SHALL NOT be silently dropped without documentation

### Requirement: Active Legacy Demo Changes MUST Be Removed From Active Set

Once cleanup is complete, active legacy demo changes (specifically `harden-demo-workspace-onboarding`) MUST be removed from the active change set. Future workflow SHALL NOT continue to rely on `harden-demo-workspace-onboarding` as an active change.

#### Scenario: OpenSpec list excludes removed changes

- **WHEN** `openspec list` is executed after cleanup completion
- **THEN** the output SHALL NOT include `harden-demo-workspace-onboarding`
- **AND** the output SHALL NOT include any other legacy demo changes marked for removal

#### Scenario: Active change directory removed

- **WHEN** cleanup Stage D (deletion) is complete
- **THEN** the directory `openspec/changes/harden-demo-workspace-onboarding/` SHALL NOT exist
- **AND** the directory `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` SHALL NOT exist

#### Scenario: Future changes do not depend on removed changes

- **WHEN** new changes are created after cleanup completion
- **THEN** they SHALL NOT reference `harden-demo-workspace-onboarding` or `add-delivery-demo-workspaces` as dependencies
- **AND** they SHALL reference `openspec/specs/delivery-demo-harness/` for demo workspace requirements

### Requirement: Demo Workspace Discovery Flow SHALL Start From Examples Directory

Demo workspace discovery flow SHALL start from `examples/README.md` and `examples/QUICKSTART.md`, not from OpenSpec change artifacts. The primary onboarding path for new users and agents SHALL be the examples directory, with `openspec/specs/delivery-demo-harness/` serving as the canonical requirements reference.

#### Scenario: New user discovers demo workspaces

- **WHEN** a new user wants to explore demo workspaces
- **THEN** they SHALL be directed to `examples/README.md` as the primary entry point
- **AND** `examples/README.md` SHALL link to `examples/QUICKSTART.md` for step-by-step onboarding
- **AND** neither document SHALL direct users to OpenSpec change artifacts as the primary discovery path

#### Scenario: Agent explores demo capabilities

- **WHEN** an AI agent is asked to demonstrate tool-governance capabilities
- **THEN** the agent SHALL consult `examples/QUICKSTART.md` for runnable demo instructions
- **AND** the agent SHALL consult `openspec/specs/delivery-demo-harness/` for canonical requirements
- **AND** the agent SHALL NOT default to reading `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`

#### Scenario: Documentation cross-references point to examples

- **WHEN** any project documentation references demo workspaces
- **THEN** cross-references SHALL point to `examples/` directory or `openspec/specs/delivery-demo-harness/`
- **AND** cross-references SHALL NOT point to legacy change artifacts unless explicitly labeled as historical context

