# Claude Code Tool Governance Plugin -- Technical Design Document

> Version: v1.1 | Updated: 2026-04-15
> Companion documents: [Development Plan](./dev_plan_en.md) | [Requirements Document](./requirements_en.md)

---

## 1 Technical Background

### 1.1 Claude Code Plugin System

A Claude Code plugin is a self-contained directory that can package skills, hooks, agents, MCP servers, LSP servers, and other components. Plugins declare metadata and component paths through the `.claude-plugin/plugin.json` manifest.

**Key specification points** (reference: [Plugins Reference](https://code.claude.com/docs/en/plugins-reference), [ivan-magda/claude-code-plugin-template](https://github.com/ivan-magda/claude-code-plugin-template)):

- `plugin.json` is the only file placed inside the `.claude-plugin/` directory
- skills/, hooks/, agents/, .mcp.json are placed in the plugin root directory
- After plugin installation, Claude Code automatically connects to the plugin's declared MCP Server at session startup
- Plugin hooks execute in parallel with user hooks
- Skills in plugins are automatically registered under the `plugin-name:skill-name` namespace
- `${CLAUDE_PLUGIN_ROOT}` points to the plugin root directory, `${CLAUDE_PLUGIN_DATA}` points to the persistent data directory

### 1.2 Claude Code Hooks System

Hooks are event handlers triggered by Claude Code at key lifecycle points (reference: [Hooks Reference](https://code.claude.com/docs/en/hooks)). Core events used by this project:

| Event | Trigger Timing | Available Capabilities |
|-------|---------------|----------------------|
| **SessionStart** | Session begins | Inject additionalContext |
| **UserPromptSubmit** | After user message sent, before model response | Inject additionalContext (**corresponds to Skill-Hub's wrap_model_call, fires every turn**) |
| **PreToolUse** | Before tool call | allow/deny/ask + updatedInput + additionalContext |
| **PostToolUse** | After successful tool call | additionalContext / block |

Hook input is received as JSON via stdin (command type) or HTTP POST body; output is returned as JSON via stdout.

**PreToolUse output format**:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "explanation text",
    "updatedInput": {},
    "additionalContext": "additional context injected to model"
  }
}
```

### 1.3 MCP (Model Context Protocol)

MCP Server exposes tools to Claude through a standard protocol. This project uses a stdio-mode Python MCP Server (based on [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)), requiring Python 3.10+, SDK 1.2.0+.

**Key constraint**: Claude Code's support for MCP `tools/list_changed` dynamic refresh is not yet fully stable. Therefore, this project adopts a **fixed meta-tool surface + server-side sub-capability dispatch** strategy.

### 1.4 Skill-Hub Project Experience

The governance mechanisms of this project are directly derived from Skill-Hub project practices (see `Skill-Hub Project Prep Edition.md`, `Handwritten Skills Long Edition.md`):

- **Dual-plane architecture**: Separation of knowledge plane (read_skill) and execution plane (enable_skill)
- **Middleware governance points**: Intercept and rewrite tools and prompt before model calls
- **State-driven tool rewriting**: active_tools recalculated each turn based on current skills_loaded
- **LRU/TTL caching**: Layered caching for skill metadata and document content

---

## 2 Overall Architecture

### 2.1 Three-Layer Architecture

```
+------------------------------------------------------+
|                  Claude Code Host                      |
|  +--------+  +--------+  +----------+  +----------+ |
|  | Model  |  | Built- |  | Other    |  | Other    | |
|  |        |  | in     |  | MCP      |  | Plugins  | |
|  |        |  | Tools  |  | Servers  |  |          | |
|  +---+----+  +--------+  +----------+  +----------+ |
|      |                                                |
|  +---+-----------------------------------------------+  |
|  |             Plugin Adapter Layer                    |  |
|  |  +----------+  +-----------+  +-------------+ |  |
|  |  | MCP      |  | Hooks     |  | Skills      | |  |
|  |  | Server   |  | Handler   |  | (SKILL.md)  | |  |
|  |  | (6 meta- |  | (event    |  | (knowledge  | |  |
|  |  |  tools)  |  |  intercept)|  |  entry)     | |  |
|  |  +----+-----+  +-----+-----+  +-------------+ |  |
|  +-------+---------------+-----------------------+  |
|          |               |                          |
|  +-------+---------------+-----------------------+  |
|  |           Governance Core Layer                 |  |
|  |  +------------+  +----------+  +------------+ |  |
|  |  | Skill      |  | State    |  | Policy     | |  |
|  |  | Indexer    |  | Manager  |  | Engine     | |  |
|  |  +------------+  +----------+  +------------+ |  |
|  |  | Tool       |  | Grant    |  | SQLite     | |  |
|  |  | Rewriter   |  | Manager  |  | Store      | |  |
|  |  +------------+  +----------+  +------------+ |  |
|  +------------------------------------------------+  |
+------------------------------------------------------+
```

**Layer responsibilities**:

1. **Plugin Adapter Layer**: Responsible for communicating with the Claude Code host. MCP Server exposes meta-tools for model calls; Hooks Handler processes lifecycle events; Skills provides the knowledge plane entry point.
2. **Governance Core Layer**: Pure Python logic with no dependency on Claude Code-specific APIs. Responsible for skill indexing, state management, policy evaluation, tool rewriting, authorization management, and persistence. Decoupled from the host platform for potential reuse with other editors in the future.

### 2.2 Data Flow

The data flow for a complete governance process is as follows:

```
[SessionStart]
    -> hook_handler.py receives event JSON (stdin)
    -> state_manager.load_or_init(session_id)
    -> grant_manager.cleanup_expired()
    -> skill_indexer.build_index()
    -> tool_rewriter.generate_context_summary()
    -> Return {additionalContext: "skill catalog summary"} (stdout)

[Model calls list_skills]
    -> mcp_server.py receives MCP request
    -> skill_indexer.list_skills()
    -> Return skill metadata list

[Model calls read_skill("db-ops")]
    -> skill_indexer.read_skill("db-ops")
    -> Check LRU/TTL cache -> hit: return directly
    -> Miss: read SKILL.md, parse and cache
    -> Return complete SOP

[Model calls enable_skill("db-ops", scope="session", ttl=3600)]
    -> policy_engine.evaluate("db-ops", session_state)
    -> risk level -> low -> auto grant
    -> grant_manager.create_grant(...)
    -> state_manager.add_to_skills_loaded("db-ops")
    -> tool_rewriter.recompute_active_tools(session_state)
    -> Return {granted: true, allowed_tools: [...]}

[Model calls run_skill_action("db-ops", "query", {sql: "..."})]
    -> Verify grant validity
    -> Verify op is in allowed_ops
    -> Dispatch to execution logic
    -> Return execution result

[PreToolUse Hook]
    -> hook_handler.py receives event JSON
    -> state_manager.get_active_tools(session_id)
    -> tool_name in active_tools?
        -> Yes -> {permissionDecision: "allow"}
        -> No  -> {permissionDecision: "deny", reason: "..."}
```

---

## 3 Module Design

### 3.1 Data Models (`src/tool_governance/models/`)

All data models are defined using Pydantic v2 BaseModel.

#### 3.1.1 Skill Model (`skill.py`)

```python
from pydantic import BaseModel

class StageDefinition(BaseModel):
    """Definition of a stage within a skill"""
    stage_id: str                          # Stage identifier (e.g., "analysis", "execution")
    description: str                       # Stage description
    allowed_tools: list[str]               # Tools allowed in this stage

class SkillMetadata(BaseModel):
    """Skill metadata, parsed from SKILL.md frontmatter"""
    skill_id: str                          # Unique identifier
    name: str                              # Display name
    description: str                       # Brief description
    risk_level: Literal["low", "medium", "high"] = "low"
    allowed_tools: list[str] = []          # Tool allowlist (used when no stages)
    allowed_ops: list[str] = []            # Allowed operation names
    stages: list[StageDefinition] = []     # Stage definitions (optional; when stages exist, allowed_tools are taken per stage)
    default_ttl: int = 3600                # Default TTL (seconds)
    source_path: str                       # SKILL.md file path
    version: str = "1.0.0"                 # Version number

class SkillContent(BaseModel):
    """Full skill content (returned by read_skill)"""
    metadata: SkillMetadata
    sop: str                               # SOP body (Markdown)
    examples: list[str] = []               # Usage examples
```

#### 3.1.2 Grant Model (`grant.py`)

```python
from datetime import datetime
from pydantic import BaseModel

class Grant(BaseModel):
    """Authorization record created by a single enable_skill call"""
    grant_id: str                          # UUID
    session_id: str
    skill_id: str
    allowed_ops: list[str]                 # Operations authorized by this grant
    scope: Literal["turn", "session"] = "session"
    ttl_seconds: int
    status: Literal["active", "expired", "revoked"] = "active"
    granted_by: Literal["auto", "user", "policy"] = "auto"
    reason: str | None = None
    created_at: datetime
    expires_at: datetime | None
```

#### 3.1.3 SessionState Model (`state.py`)

```python
from pydantic import BaseModel

class LoadedSkillInfo(BaseModel):
    """Snapshot info for an enabled skill (with version)"""
    skill_id: str
    version: str                                       # Version at time of enabling
    current_stage: str | None = None                   # Current stage (None if no stages)
    last_used_at: datetime | None = None               # Last used time (for LRU reclamation)

class SessionState(BaseModel):
    """Session-level governance state"""
    session_id: str
    skills_metadata: dict[str, SkillMetadata] = {}     # Skill index (session-level snapshot)
    skills_loaded: dict[str, LoadedSkillInfo] = {}     # Enabled skills: skill_id -> snapshot info (with version)
    active_tools: list[str] = []                       # Current visible tool list
    active_grants: dict[str, Grant] = {}               # skill_id -> Grant
    created_at: datetime
    updated_at: datetime
```

#### 3.1.4 Policy Model (`policy.py`)

```python
from pydantic import BaseModel

class SkillPolicy(BaseModel):
    """Policy configuration for a single skill"""
    skill_id: str
    auto_grant: bool = True                # Whether to auto-grant
    require_reason: bool = False           # Whether a reason is required
    max_ttl: int = 7200                    # Maximum TTL
    approval_required: bool = False        # Whether user approval is required

class GovernancePolicy(BaseModel):
    """Global governance policy"""
    default_risk_thresholds: dict[str, str] = {
        "low": "auto",       # Auto-grant
        "medium": "reason",  # Reason required
        "high": "approval"   # Approval required
    }
    default_ttl: int = 3600
    default_scope: str = "session"
    skill_policies: dict[str, SkillPolicy] = {}   # skill_id -> policy
    blocked_tools: list[str] = []                  # Globally blocked tools
```

### 3.2 Core Modules (`src/tool_governance/core/`)

#### 3.2.1 skill_indexer.py

**Responsibility**: Scan the skills/ directory, parse YAML frontmatter, build the skill index.

**Core interfaces**:

```python
class SkillIndexer:
    def __init__(self, skills_dir: str, cache: TTLCache):
        """Initialize with skills directory and cache"""

    def build_index(self) -> dict[str, SkillMetadata]:
        """Scan directory, parse all SKILL.md files, return skill_id -> SkillMetadata"""

    def list_skills(self) -> list[SkillMetadata]:
        """Return metadata summaries for all skills"""

    def read_skill(self, skill_id: str) -> SkillContent | None:
        """Read complete content of a specified skill (cache-first)"""
```

**Implementation notes**:
- Use `yaml.safe_load` to parse frontmatter, skip entries with missing fields
- File size limit (default 100KB), truncate or skip if exceeded
- Parse failures are logged but do not affect other skills
- Metadata cached in SessionState (session-level), document content uses TTLCache (process-level)

#### 3.2.2 state_manager.py

**Responsibility**: Manage creation, loading, updating, and persistence of session-level governance state.

**Core interfaces**:

```python
class StateManager:
    def __init__(self, store: SQLiteStore):
        """Initialize with injected persistent storage"""

    def load_or_init(self, session_id: str) -> SessionState:
        """Load existing state or create new state"""

    def save(self, state: SessionState) -> None:
        """Persist state to SQLite"""

    def add_to_skills_loaded(self, state: SessionState, skill_id: str) -> None:
        """Add a skill to the enabled list"""

    def remove_from_skills_loaded(self, state: SessionState, skill_id: str) -> None:
        """Remove a skill from the enabled list"""

    def get_active_tools(self, state: SessionState) -> list[str]:
        """Return current active_tools"""
```

**Implementation notes**:
- State is serialized as JSON and stored in SQLite
- `updated_at` timestamp is updated with every state change
- `active_tools` is not maintained incrementally; it is recalculated from current `skills_loaded` each time

#### 3.2.3 policy_engine.py

**Responsibility**: Evaluate whether a skill can be enabled based on policy configuration.

**Core interfaces**:

```python
class PolicyEngine:
    def __init__(self, policy: GovernancePolicy):
        """Initialize with loaded policy configuration"""

    def evaluate(
        self,
        skill_id: str,
        skill_meta: SkillMetadata,
        state: SessionState,
        reason: str | None = None
    ) -> PolicyDecision:
        """Evaluate whether enabling a skill is allowed, return decision"""

    def is_tool_allowed(
        self,
        tool_name: str,
        state: SessionState
    ) -> bool:
        """Check if a tool is in the current active_tools"""
```

```python
class PolicyDecision(BaseModel):
    allowed: bool
    decision: Literal["auto", "reason_required", "approval_required", "denied"]
    reason: str | None = None
```

**Evaluation logic**:
1. Check if the skill is on the global blocklist -> if so, directly denied
2. Check if there is a skill-specific policy -> use it with priority
3. Match risk_level against default thresholds: low -> auto, medium -> reason, high -> approval
4. If decision is reason_required but no reason provided -> denied
5. If decision is approval_required -> return requiring user confirmation (handled at Hook layer)

#### 3.2.4 prompt_composer.py (new)

**Responsibility**: Generate prompt fragments for injection into the model context. Corresponds to PromptComposer in the Skill-Hub project, called during each UserPromptSubmit turn.

**Core interfaces**:

```python
class PromptComposer:
    # No constructor arguments — PromptComposer is a stateless
    # formatter.  All inputs arrive via SessionState on each call.

    def compose_context(self, state: SessionState) -> str:
        """Generate complete additionalContext (≤ 800 chars), composed of:
        1. Skill catalog summary (unenabled skills show only name and description)
        2. Currently enabled skills and their active_tools
        3. Authorization guidance (for more capabilities, use read_skill -> enable_skill)
        Hard-truncates with "..." when the combined text exceeds the budget.
        """

    def compose_skill_catalog(self, state: SessionState) -> str:
        """Generate only the skill catalog summary portion (for SessionStart initial injection)"""

    def compose_active_tools_prompt(self, state: SessionState) -> str:
        """Generate current available tools description, guiding the model to use them correctly"""
```

**Implementation notes**:
- Output kept under 800 characters (skill catalog summary + active tools hint + guidance text)
- Enabled skills show more details (current stage, allowed_tools list)
- Unenabled skills show only name, description, and risk level
- Stateless class: no `SkillIndexer` dependency is injected at construction time. The skill catalog is read from `state.skills_metadata` which the hook handler populates via the indexer before calling `compose_context`.

#### 3.2.5 tool_rewriter.py

**Responsibility**: Compute active_tools based on skills_loaded + current_stage.

**Core interfaces**:

```python
class ToolRewriter:
    def __init__(self, blocked_tools: list[str] | None = None):
        """Initialize with an optional global deny-list of tool names
        (applied last, after meta + stage tools are unioned)."""

    def recompute_active_tools(self, state: SessionState) -> list[str]:
        """Iterate skills_loaded, take the union of allowed_tools by current_stage, filter blocklist.
        If a skill has no stage definitions, use the entire skill's allowed_tools.
        If a skill has stage definitions but current_stage is None, use the first stage's allowed_tools.
        Mutates ``state.active_tools`` in place; returns the new list."""

    @staticmethod
    def get_stage_tools(skill_meta: SkillMetadata, current_stage: str | None) -> list[str]:
        """Get allowed_tools for a specified skill at a specified stage
        (stateless — no ToolRewriter instance needed)."""
```

**Implementation notes**:
- `active_tools` = meta-tools ∪ ⋃{get_stage_tools(skill, stage) | skill ∈ skills_loaded} - blocked_tools
- Meta-tools are always visible, not affected by skills_loaded
- **Recalculated from current state each turn, no incremental append** (corresponding to Skill-Hub design principle)
- If a skill has stages definitions, use `LoadedSkillInfo.current_stage` to get the corresponding stage's allowed_tools
- Update `state.active_tools` after each recalculation
- `ToolRewriter` takes an optional `blocked_tools` list instead of a `SkillIndexer` handle; skill metadata is read from `state.skills_metadata`, so the indexer is not needed at construction time.

#### 3.2.6 grant_manager.py

**Responsibility**: Manage the lifecycle of authorization records.

**Core interfaces**:

```python
class GrantManager:
    def __init__(self, store: SQLiteStore):
        """Initialize"""

    def create_grant(
        self,
        session_id: str,
        skill_id: str,
        allowed_ops: list[str],
        scope: str,
        ttl: int,
        granted_by: str,
        reason: str | None
    ) -> Grant:
        """Create a new authorization record"""

    def revoke_grant(self, grant_id: str) -> None:
        """Revoke a specified authorization"""

    def cleanup_expired(self, session_id: str) -> list[str]:
        """Clean up expired authorizations, return list of cleaned skill_ids"""

    def get_active_grants(self, session_id: str) -> list[Grant]:
        """Get all active authorizations in a session"""

    def is_grant_valid(self, session_id: str, skill_id: str) -> bool:
        """Check if the authorization for a specified skill is still valid"""
```

### 3.3 Storage Module (`src/tool_governance/storage/`)

#### 3.3.1 sqlite_store.py

**Responsibility**: SQLite-based persistent storage; database file located at `${CLAUDE_PLUGIN_DATA}/governance.db`.

**Database tables**:

```sql
-- Session state table
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,           -- SessionState serialized JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Authorization records table
CREATE TABLE grants (
    grant_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    allowed_ops TEXT NOT NULL,           -- JSON array
    scope TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    granted_by TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

-- Audit log table (append-only)
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,            -- skill.list / skill.read / skill.enable / tool.call etc.
    skill_id TEXT,
    tool_name TEXT,
    decision TEXT,                       -- allow / deny / ask
    detail TEXT,                         -- JSON additional info
    created_at TEXT NOT NULL
);

CREATE INDEX idx_grants_session ON grants(session_id, status);
CREATE INDEX idx_audit_session ON audit_log(session_id);
CREATE INDEX idx_audit_event ON audit_log(event_type);
```

### 3.4 Cache Module (`src/tool_governance/utils/cache.py`)

**Two-layer caching strategy** (corresponding to Skill-Hub project practice):

| Cache Layer | Storage Location | Content | Invalidation Strategy |
|-------------|-----------------|---------|----------------------|
| Metadata cache | SessionState.skills_metadata | Skill index (name, description, allowed_tools, etc.) | Session-level: rebuilt on new session, explicit refresh |
| Document cache | In-process TTLCache | read_skill parse results (SOP body) | TTL (default 300s) + LRU (default maxsize=100) |

```python
from cachetools import TTLCache

# Document cache: TTL 5 minutes, max 100 cached skill documents
skill_doc_cache = TTLCache(maxsize=100, ttl=300)
```

---

## 4 Plugin Adapter Layer Design

### 4.1 plugin.json

```json
{
  "name": "tool-governance-plugin",
  "version": "0.1.0",
  "description": "Runtime tool governance for Claude Code: progressive disclosure, dynamic authorization, and lifecycle management.",
  "author": {
    "name": "Your Name"
  },
  "license": "MIT",
  "keywords": ["governance", "tools", "skills", "authorization", "security"],
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json"
}
```

### 4.2 .mcp.json

```json
{
  "mcpServers": {
    "tool-governance": {
      "command": "python3",
      "args": ["${CLAUDE_PLUGIN_ROOT}/src/tool_governance/mcp_server.py"],
      "env": {
        "GOVERNANCE_DATA_DIR": "${CLAUDE_PLUGIN_DATA}",
        "GOVERNANCE_SKILLS_DIR": "${CLAUDE_PLUGIN_ROOT}/skills"
      }
    }
  }
}
```

> **[Uncertain]** The `command` field in `.mcp.json` may need to use `python` instead of `python3` on Windows. Platform adaptation or a wrapper script is needed during implementation.

### 4.3 hooks/hooks.json

```json
{
  "SessionStart": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/tool_governance/hook_handler.py",
          "timeout": 5000
        }
      ]
    }
  ],
  "UserPromptSubmit": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/tool_governance/hook_handler.py",
          "timeout": 3000
        }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/tool_governance/hook_handler.py",
          "timeout": 3000
        }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/tool_governance/hook_handler.py",
          "timeout": 3000
        }
      ]
    }
  ]
}
```

**hook_handler.py entry logic**:

```python
import json
import sys

def main():
    # Read event JSON from stdin
    input_data = json.loads(sys.stdin.read())
    event_name = input_data.get("event")

    if event_name == "SessionStart":
        result = handle_session_start(input_data)
    elif event_name == "UserPromptSubmit":
        result = handle_user_prompt_submit(input_data)  # Per-turn Prompt/Tool rewriting
    elif event_name == "PreToolUse":
        result = handle_pre_tool_use(input_data)
    elif event_name == "PostToolUse":
        result = handle_post_tool_use(input_data)
    else:
        result = {}

    # Output result JSON to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

### 4.4 skills/governance/SKILL.md

```markdown
---
description: "Manage tool governance: discover, read, and enable skills to control the tool surface."
allowed_tools:
  - mcp__tool-governance__list_skills
  - mcp__tool-governance__read_skill
  - mcp__tool-governance__enable_skill
  - mcp__tool-governance__disable_skill
  - mcp__tool-governance__grant_status
  - mcp__tool-governance__run_skill_action
---

# Tool Governance

This skill manages progressive disclosure and authorization of capabilities.

## Workflow

1. Use `list_skills` to discover available skills and their risk levels
2. Use `read_skill(skill_id)` to understand a skill's SOP, boundaries, and allowed tools
3. Use `enable_skill(skill_id)` to explicitly authorize a skill for the current session
4. Use `run_skill_action(skill_id, op, args)` to execute operations within an enabled skill
5. Use `grant_status` to check current authorizations
6. Use `disable_skill(skill_id)` to revoke authorization when no longer needed

## Rules

- Never attempt to use tools outside of enabled skills
- Always read a skill before enabling it
- Prefer the narrowest scope and shortest TTL that satisfies the task
- If a tool call is denied, follow the authorization flow instead of retrying
```

### 4.5 MCP Server Meta-Tool Definitions

The MCP Server exposes 8 fixed meta-tools:

| Tool Name | Input Parameters | Returns | Description |
|-----------|-----------------|---------|-------------|
| `list_skills` | None | `SkillMetadata[]` | List all available skills |
| `read_skill` | `skill_id: str` | `SkillContent` | Read a skill's complete SOP |
| `enable_skill` | `skill_id: str, reason?: str, scope?: str, ttl?: int` | `{granted: bool, allowed_tools: str[]}` | Enable a skill |
| `disable_skill` | `skill_id: str` | `{disabled: bool}` | Disable a skill |
| `grant_status` | None | `Grant[]` | View current authorization status |
| `run_skill_action` | `skill_id: str, op: str, args?: object` | `{result: any}` | Execute a skill operation |
| `change_stage` | `skill_id: str, stage_id: str` | `{changed: bool, new_active_tools: str[]}` | Switch skill stage, update current_stage and active_tools |
| `refresh_skills` | None | `{refreshed: bool, skill_count: int}` | Force refresh skill index (clear cache and re-scan) |

MCP Server implementation is based on the `mcp` Python SDK, using stdio transport:

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("tool-governance")

@server.tool()
async def list_skills() -> list[dict]:
    """List all available skills with their metadata."""
    ...

@server.tool()
async def read_skill(skill_id: str) -> dict:
    """Read the full SOP and details of a specific skill."""
    ...

# ... other tool definitions

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)
```

---

## 5 LangChain Integration Plan

### 5.1 Integration Approach

LangChain is used to wrap core governance operations as Tools, facilitating composition and testing within the governance core layer.

```python
from langchain_core.tools import tool

@tool
def list_skills_tool() -> list[dict]:
    """List all available skills for the current session."""
    indexer = get_skill_indexer()
    return [m.model_dump() for m in indexer.list_skills()]

@tool
def read_skill_tool(skill_id: str) -> dict:
    """Read the complete SOP of a skill."""
    indexer = get_skill_indexer()
    content = indexer.read_skill(skill_id)
    if content is None:
        return {"error": f"Skill '{skill_id}' not found"}
    return content.model_dump()

@tool
def enable_skill_tool(
    skill_id: str,
    reason: str = "",
    scope: str = "session",
    ttl: int = 3600
) -> dict:
    """Enable a skill for the current session."""
    state = get_current_state()
    decision = policy_engine.evaluate(skill_id, state)
    if not decision.allowed:
        return {"granted": False, "reason": decision.reason}
    grant = grant_manager.create_grant(...)
    state_manager.add_to_skills_loaded(state, skill_id)
    active = tool_rewriter.recompute_active_tools(state)
    return {"granted": True, "allowed_tools": active}
```

### 5.2 Scope of LangChain Usage

| Use Case | LangChain Component | Description |
|----------|-------------------|-------------|
| Meta-tool wrapping | `@tool` decorator | Wrap governance interfaces as standard Tools |
| Prompt templates | `ChatPromptTemplate` | Generate skill catalog summaries and guidance prompts |
| Callback tracing | `CallbackHandler` | Connect to observability platforms like Langfuse (V2) |

> **Note**: LangChain is primarily used in this project as a **tool definition and prompt management framework**, without introducing heavy components like Agent/Chain/Memory. The governance logic itself is deterministic and does not require LLM participation in decision-making.

---

## 6 Key Process Detailed Design

### 6.1 SessionStart Processing Flow

```python
def handle_session_start(input_data: dict) -> dict:
    session_id = input_data.get("session_id", generate_session_id())

    # 1. Load or initialize state
    state = state_manager.load_or_init(session_id)

    # 2. Reclaim expired Grants
    expired_skills = grant_manager.cleanup_expired(session_id)
    for skill_id in expired_skills:
        state_manager.remove_from_skills_loaded(state, skill_id)

    # 3. Build/refresh skill index
    if not state.skills_metadata:
        state.skills_metadata = skill_indexer.build_index()

    # 4. Recalculate active_tools
    state.active_tools = tool_rewriter.recompute_active_tools(state)

    # 5. Persist state
    state_manager.save(state)

    # 6. Generate additionalContext
    summary = tool_rewriter.generate_context_summary(state)

    return {
        "additionalContext": summary
    }
```

### 6.2 UserPromptSubmit Processing Flow (corresponds to wrap_model_call)

> **This hook is the core control point of the entire governance mechanism**, corresponding to `wrap_model_call` in Skill-Hub.
> Triggered after each user message, responsible for: 1) recalculating active_tools; 2) injecting skill state into additionalContext.

```python
def handle_user_prompt_submit(input_data: dict) -> dict:
    session_id = input_data.get("session_id")
    state = state_manager.load_or_init(session_id)

    # 1. Reclaim grants expired in this turn
    expired_skills = grant_manager.cleanup_expired(session_id)
    for skill_id in expired_skills:
        state_manager.remove_from_skills_loaded(state, skill_id)

    # 2. Recalculate active_tools based on latest skills_loaded + current_stage (per-turn recalculation, not append)
    state.active_tools = tool_rewriter.recompute_active_tools(state)

    # 3. Use PromptComposer to generate additionalContext
    context = prompt_composer.compose_context(state)

    # 4. Persist state
    state_manager.save(state)

    # 5. Record audit
    audit_log.record("prompt.submit", session_id,
                     detail={"active_skills": list(state.skills_loaded.keys()),
                             "active_tools_count": len(state.active_tools)})

    return {
        "additionalContext": context
    }
```

**compose_context output example**:

```
[Tool Governance] Current session state:
- Available skills: db-ops (enabled, stage: analysis), code-edit (not enabled), verify (not enabled)
- Current active tools: sql_query, logs_search, slow_query_analysis
- For more capabilities, use list_skills -> read_skill -> enable_skill
```

### 6.3 PreToolUse Processing Flow

```python
def handle_pre_tool_use(input_data: dict) -> dict:
    session_id = input_data.get("session_id")
    tool_name = input_data.get("tool_name")

    state = state_manager.load_or_init(session_id)

    # Check if it's a meta-tool (always allow)
    META_TOOLS = {"list_skills", "read_skill", "enable_skill",
                  "disable_skill", "grant_status", "run_skill_action",
                  "change_stage", "refresh_skills"}
    # MCP tool name format: mcp__tool-governance__<tool_name>
    short_name = extract_tool_name(tool_name)

    if short_name in META_TOOLS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }

    # Check if the tool is in active_tools
    if policy_engine.is_tool_allowed(tool_name, state):
        # Record audit
        audit_log.record("tool.call", session_id, tool_name=tool_name, decision="allow")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"
            }
        }
    else:
        audit_log.record("tool.call", session_id, tool_name=tool_name, decision="deny")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Tool '{tool_name}' is not in active_tools. "
                    "Please use read_skill and enable_skill to authorize the required skill first.",
                "additionalContext": "To use this tool, first discover available skills "
                    "with list_skills, then read_skill to understand the workflow, "
                    "then enable_skill to authorize."
            }
        }
```

> **[Uncertain]** The specific field name for `session_id` in hook input may vary by Claude Code version. This needs to be confirmed during implementation based on the actual hook input schema. If session_id is not present in the hook input, another identifier (such as conversation_id) may need to be used, or one can be self-generated and associated via file/SQLite.

---

## 7 Technology Selection and Dependencies

### 7.1 Python Dependencies

```toml
# pyproject.toml [project.dependencies]
[project]
name = "tool-governance"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "mcp>=1.2.0",              # MCP Python SDK (stdio server)
    "pydantic>=2.0",            # Data models and validation
    "langchain-core>=0.3",      # Tool wrapping and prompt templates
    "cachetools>=5.0",          # LRU/TTL caching
    "pyyaml>=6.0",              # YAML frontmatter parsing
]

[project.optional-dependencies]
server = [
    "fastapi>=0.100",           # Optional HTTP hook service
    "uvicorn>=0.20",
]
observability = [
    "langfuse>=2.0",            # Optional observability
]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",                # Linter
    "mypy>=1.0",                # Type checking
]
```

### 7.2 Technology Selection Rationale

| Component | Choice | Rationale |
|-----------|--------|-----------|
| MCP SDK | `mcp` (Python) | Official SDK, stdio transport, native integration with Claude Code |
| Data models | Pydantic v2 | Type safety, convenient serialization/deserialization, FastAPI compatible |
| LangChain | langchain-core | Lightweight Tool wrapping without the full Agent stack |
| Caching | cachetools | Pure Python, zero external dependencies, supports LRU/TTL |
| Persistence | SQLite | Built into Python, no external services required, suitable for single-machine plugin scenarios |
| YAML parsing | PyYAML | Standard library-level stability, safe_load prevents injection |

---

## 8 Security Design

### 8.1 Input Security

- SKILL.md treated as untrusted input:
  - `yaml.safe_load()` for frontmatter parsing
  - File size limit (default 100KB)
  - Description field truncation (default 500 characters)
  - Parse failures only warn, do not affect other skills

### 8.2 Permission Security

- Meta-tools (list_skills, etc.) are always available, no permission interception
- Underlying tool calls must pass the PreToolUse hook active_tools check
- High-risk skills (risk_level=high) require user confirmation for enable_skill
- Policy configuration files cannot be modified via MCP tools, only through file editing

### 8.3 Data Security

- SQLite database stored in the `${CLAUDE_PLUGIN_DATA}` directory, following Claude Code's data isolation
- Audit log table is append-only (no DELETE/UPDATE interface provided)
- The reason field in Grants does not store sensitive information

---

## 9 Testing Strategy

### 9.1 Unit Tests

| Module | Test Focus |
|--------|-----------|
| skill_indexer | Directory scanning, frontmatter parsing, missing field handling, large file skipping, cache hits |
| state_manager | State creation/loading/saving, skills_loaded add/remove, serialization consistency |
| policy_engine | Decisions for each risk level, blocklist interception, policy override priority |
| tool_rewriter | active_tools calculation (union, dedup, blocklist exclusion), prompt generation |
| grant_manager | Grant creation/expiry/revocation, TTL calculation, cleanup_expired |
| sqlite_store | CRUD operations, audit log writing, index effectiveness |

### 9.2 Integration Tests

- Simulate complete flow: SessionStart -> list_skills -> read_skill -> enable_skill -> run_skill_action
- Interception test: attempt to call an unauthorized tool, verify PreToolUse returns deny
- TTL test: create a short-TTL grant, wait for expiry, then verify cleanup
- Multi-skill test: enable multiple skills simultaneously, verify active_tools is the correct union

### 9.3 Local Validation

Load the plugin in Claude Code and manually verify:
1. Plugin loads without errors
2. MCP Server connects normally, 6 meta-tools are discoverable
3. Hook events fire correctly
4. Complete governance flow runs successfully

---

## 10 Uncertainties Summary

The following items have uncertainties at the current design stage and need to be verified and confirmed during implementation:

| # | Uncertainty | Affected Scope | Suggested Approach |
|---|------------|----------------|-------------------|
| U1 | Specific field name and format for session_id in hook input | hook_handler.py | Print actual hook input JSON during implementation to confirm fields |
| U2 | Actual path of `${CLAUDE_PLUGIN_DATA}` on different platforms | sqlite_store.py | Test on Windows/macOS/Linux |
| U3 | `python3` command may not exist on Windows | .mcp.json, hooks.json | Use wrapper script or conditional logic |
| U4 | Execution order and priority of plugin hooks vs. user hooks | hook_handler.py | Test and verify; governance hooks designed as read-only checks |
| U5 | How `run_skill_action` delegates to actual tool execution | mcp_server.py | V1 provides framework and examples; specific execution logic per skill definition |
| U6 | MCP Server process lifecycle management | .mcp.json | Claude Code should manage automatically; needs verification |
| U7 | Specific plugin installation command and process | README.md | Reference actual version's CLI documentation |
| U8 | PreToolUse hook matcher format for MCP tools | hooks.json | MCP tool name format is `mcp__<server>__<tool>`; verify whether matcher supports wildcards |

---

## 10-B Phase 1–3 Hardening Sync Notes (phase13-hardening-and-doc-sync)

> Sync-only entries from the Stage A / B hardening round. Body text in
> earlier sections is unchanged; edits required there are tracked in
> Stage C. These notes are the canonical record of behavioural deltas
> that already landed in code.

### Stage A — run_skill_action deny-by-default (D2)

- `run_skill_action` denies when `state.skills_metadata[skill_id]` is
  `None`. Response: `{"error": "Skill '…' metadata unavailable; operation denied"}`.
- Audit: one `skill.action.deny` record per denied call, with
  `detail={"op": <op>, "reason": "meta_missing"}`. No dispatch, no
  grant/state mutation.

### Stage A — PostToolUse single-stamp (D1)

- `handle_post_tool_use` stamps `last_used_at` on exactly one skill per
  event. Top-level `allowed_tools` match beats stage-level match; the
  first matching skill in iteration order wins. Later skills cannot
  overwrite the timestamp.

### Stage B — enable_skill entry-point parity (D6)

- `enable_skill_tool` (LangChain) and `mcp_server.enable_skill` apply
  the same coercions: `scope = "turn" if scope == "turn" else "session"`;
  `granted_by = "auto" if decision.decision == "auto" else "policy"`.
- Invariant: for identical inputs both entry points build equivalent
  `Grant` objects and write `state.active_grants[skill_id]` identically.
- An unrecognised `scope` no longer raises from the LangChain path; it
  coerces to `"session"` on both paths.

### Stage B — refresh_skills single scan (D3)

- `refresh_skills` performs exactly one directory scan per call.
  `SkillIndexer.current_index()` is the read-only accessor used after
  `refresh()` to read the freshly-built index without a second
  `build_index()` invocation.
- Response shape unchanged: `{"refreshed": True, "skill_count": count}`.

### Stage B — grant.revoke audit event (D7)

- New event `grant.revoke`, emitted by `GrantManager.revoke_grant()`
  exactly once per revocation. Fields: `session_id`, `skill_id`,
  `event_type="grant.revoke"`, `detail={"grant_id": ..., "reason": ...}`.
- `revoke_grant(grant_id, reason="explicit")` — `reason` defaults to
  `"explicit"`; callers MAY pass other discriminators for future
  revoke-paths (e.g. turn/session scope revocation).
- Event-boundary invariants:
  - `skill.disable` (unchanged) — still emitted by the entry point
    after `revoke_grant()` returns. Explicit-disable ordering is
    `grant.revoke` → `skill.disable`.
  - `grant.expire` (unchanged) — still emitted by the hook-handler TTL
    sweep. `cleanup_expired` transitions status to `"expired"` directly
    and does **not** go through `revoke_grant()`; `grant.revoke` and
    `grant.expire` therefore never fire for the same grant.
  - Disabling a skill whose grant was already cleaned up emits
    `skill.disable` only (no `grant.revoke`).

### Stage C — active_grants key-semantics note (D8)

`state.active_grants: dict[str, Grant]` is keyed by **`skill_id`**, not
by `grant_id`. The authoritative `grant_id` lives inside each stored
`Grant` object (and on the DB row); the dict key is the lookup handle
used by `enable_skill` / `disable_skill` / `run_skill_action`.

Invariants held by the current implementation:

- At most one active `Grant` per `(session_id, skill_id)` pair.
  Re-enabling a skill overwrites the previous entry.
- `remove_from_skills_loaded(state, skill_id)` detaches both
  `skills_loaded[skill_id]` and `active_grants[skill_id]` atomically.
- Lifecycle events (`grant.revoke`, `grant.expire`) carry the
  authoritative `grant_id` in their audit record, so the key collision
  with `skill_id` does not affect audit correlation.

**Deferred**: re-keying `active_grants` to `grant_id` would allow
multiple simultaneous grants per skill (e.g. overlapping scopes) but
is not a current requirement and is explicitly out of scope for this
hardening round. Stale docstrings in `models/state.py` and
`core/state_manager.py` that described the dict as `grant_id`-keyed
have been corrected in code as part of this doc-sync.

### Stage C — D5 signatures, D8 note: resolved

The previous "Deferred to Stage C" bullet is now closed: Section 3.2.4
(`PromptComposer`) and Section 3.2.5 (`ToolRewriter`) signatures match
the implementation, and D8 is documented above.

---

## 11 References

- [Claude Code Plugins Reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Tools Reference](https://code.claude.com/docs/en/tools-reference)
- [Claude Code MCP Integration](https://code.claude.com/docs/en/mcp)
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Settings](https://code.claude.com/docs/en/settings)
- [ivan-magda/claude-code-plugin-template](https://github.com/ivan-magda/claude-code-plugin-template)
- [anthropics/claude-code plugins](https://github.com/anthropics/claude-code/tree/main/plugins)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- Skill-Hub Project Documentation (this project's `Skill-Hub Project Prep Edition.md`, `Handwritten Skills Long Edition.md`)
