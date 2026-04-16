# Claude Code Tool Governance Plugin -- Requirements Document

> Version: v1.1 | Updated: 2026-04-15
> Companion documents: [Development Plan](./dev_plan_en.md) | [Technical Design Document](./technical_design_en.md)

---

## 1 Project Background

### 1.1 Problem Statement

Claude Code supports extending capabilities through Plugins, MCP Servers, and Skills. As the extension ecosystem grows rapidly, the agent model faces a dramatically increasing set of candidate capabilities during each inference turn, creating the following engineering problems:

1. **Context bloat**: Large numbers of tool descriptions consume the context window, reducing the model's attention to the task itself
2. **Tool misselection**: The more candidate tools, the more likely the model is to confuse semantically similar tools, increasing misselection rates
3. **Decision instability**: The same task may produce inconsistent execution paths across different sessions due to varying tool combinations
4. **Blurred permission boundaries**: All installed tools are exposed at once, lacking the means for dynamic control by task, session, or risk level
5. **Missing state**: Claude Code currently has no built-in "capability lifecycle" management -- once tools are installed, they are permanently visible

### 1.2 Project Goals

Develop a Claude Code plugin that adds a runtime governance layer between the model and tools, achieving:

- **Progressive disclosure**: The model first sees the skill catalog, reads SOPs on demand, then explicitly authorizes
- **Dynamic authorization**: Determines whether to enable a capability based on task type, risk level, and user policies
- **State reclamation**: Authorizations have lifecycles (TTL/turn/session) and are automatically reclaimed upon expiry

### 1.3 Project Positioning

**Human-controlled automated governance runtime**: Users define governance boundaries (policies), the system automatically enforces capability exposure, authorization verification, and lifecycle progression at runtime, with high-risk actions explicitly escalated to human confirmation.

- Policy definition phase: manual-leaning (users set rules)
- Runtime governance phase: automation-leaning (system enforces rules)
- Escalation approval phase: human-leaning (high-risk requires confirmation)

---

## 2 User Roles

| Role | Description | Core Need |
|------|-------------|-----------|
| **Plugin User** | Developer performing coding, debugging, and knowledge tasks in Claude Code | Accurate, safe, and efficient tool usage; no interference from irrelevant tools |
| **Team Administrator** | Management role configuring team-level policies and approving high-risk operations | Unified governance rules; auditability; compliance |
| **Plugin Developer** | Developer maintaining the governance plugin itself or building on top of this framework | Maintainable code; decoupled architecture; easy extensibility |

---

## 3 Governance Objects

The governance objects that this plugin needs to manage include the following 6 categories, covering the major capability types in the current Claude Code extension ecosystem:

| Governance Object | Source | Description |
|-------------------|--------|-------------|
| **Built-in Tools** | Claude Code native | Bash, Read, Edit, Write, WebFetch, WebSearch, Agent, etc. |
| **MCP Tools** | External MCP Servers | Third-party tools connected via MCP protocol |
| **Skills** | Plugin or project-level skills/ directory | Structured SOPs + tool allowlists extending Claude's capabilities |
| **Subagents** | Created by Agent tool | Sub-task executors with independent context and tool restrictions |
| **Plugin Components** | Installed plugins | A plugin may contain skills + hooks + MCP + agents |
| **MCP Prompts/Resources** | MCP Servers | Context data and message templates affecting what the model "knows" |

> **[Uncertain]** The current version prioritizes governance of Skills and MCP Tools. Built-in tool governance (e.g., Bash command allowlists) can be covered through policy configuration without deep modifications; subagent tool restrictions leverage Claude Code's native `tools`/`disallowedTools` mechanism.

---

## 4 Governance Dimensions

Complete tool governance needs to cover the following 8 dimensions. V1 focuses on the first 6; dimensions 7 and 8 are optional/future enhancements.

### 4.1 Visibility Governance

**Problem**: What capabilities does Claude currently see? Are there too many?

**Requirements**:
- At session start, Claude only sees a small number of meta-tools (list_skills, read_skill, enable_skill, etc.)
- The skill catalog is injected into the system prompt in summary form, not in full
- Underlying tools for unenabled skills do not appear in the model's visible range

### 4.2 Semantic Governance

**Problem**: How does Claude understand these capabilities? Could it confuse them?

**Requirements**:
- Each skill has a clear purpose definition, applicable scenarios, and boundary descriptions
- Responsibilities between skills do not overlap, or overlapping areas have explicit priority descriptions
- The SOP returned by `read_skill` helps the model understand the correct workflow for that task type

### 4.3 Eligibility Governance

**Problem**: Which capabilities are eligible for use in the current task?

**Requirements**:
- Support recommending candidate skill sets by task type
- Irrelevant skills, even if installed, do not enter the current task's candidate pool
- Subagent capability surfaces can be trimmed independently from the main session

### 4.4 Authorization Governance

**Problem**: Who approved the use of a given capability?

**Requirements**:
- Low-risk skills can be auto-granted
- Medium-risk skills require the model to explicitly call `enable_skill` and record a reason
- High-risk skills require user confirmation (via Claude Code's permission prompt)
- Each authorization records: grantor, object, scope, time, expiration conditions

### 4.5 Lifecycle Governance

**Problem**: When does a capability become active, and when is it reclaimed?

**Requirements**:
- Authorizations have scope: `turn` (single turn) or `session` (session-level)
- Authorizations have TTL: automatically expire when time is up
- All temporary authorizations are cleaned up at session end
- Explicit revocation supported (`disable_skill`)

### 4.6 Composition Governance

**Problem**: Could multiple capabilities combined together exceed intended permissions?

**Requirements**:
- Each skill restricts usable tools via an `allowed_tools` allowlist
- Only tools corresponding to skills in `skills_loaded` appear in `active_tools`
- PreToolUse hook serves as hard interception, blocking tool calls outside the allowlist

### 4.7 Trust Governance (V2)

**Problem**: Is the source of a capability trustworthy?

> Future versions will consider: differentiating trust levels between official tools, internal team plugins, and third-party MCP Servers, and setting default risk levels accordingly.

### 4.8 Audit and Observability Governance

**Problem**: Can we clearly explain what happened after the fact?

**Requirements**:
- Record key operations: skill.list, skill.read, skill.enable, skill.disable, tool.call, grant.expire, grant.revoke, stage.change
- Each record includes: timestamp, session_id, skill_id, tool_name, decision result, reason
- **Funnel metrics**: Record data at each stage shown -> read -> enable -> tool -> task, to locate pipeline bottlenecks
- **Miscall bucketing**: Distinguish three types of miscalls: outside-allowlist calls, wrong tool within domain, correct tool but wrong parameters
- Stored in SQLite, queryable and exportable
- Integrate with Langfuse for full-chain trace/session/observation linking

---

## 5 Functional Requirements

### 5.1 Core Features (V1 Must-Have)

#### F1: Skill Catalog Retrieval -- `list_skills`

- Returns a summary list of all available skills
- Each entry includes: skill_id, name, description, risk_level, is_enabled
- Data source: scan skills/ directory + cache

#### F2: Skill Reading -- `read_skill`

- Input: skill_id
- Returns: complete SOP of the skill (applicable scenarios, step descriptions, risk notes, allowed_tools list)
- Read results are cached (LRU/TTL) to avoid redundant IO

#### F3: Skill Enabling -- `enable_skill`

- Input: skill_id, reason (optional), scope (turn/session), ttl (seconds)
- Behavior:
  1. Policy engine evaluates whether enabling is allowed (risk level, policy configuration)
  2. If allowed, creates a Grant record and updates skills_loaded
  3. Recalculates active_tools
- Output: authorization result (granted/denied) + list of allowed tools

#### F4: Skill Disabling -- `disable_skill`

- Input: skill_id
- Behavior: revokes the corresponding Grant, removes from skills_loaded, recalculates active_tools

#### F5: Authorization Status Query -- `grant_status`

- Returns a list of all active Grants for the current session
- Each entry includes: grant_id, skill_id, scope, ttl, expires_at, status

#### F6: Skill Action Execution -- `run_skill_action`

- Input: skill_id, op (operation name), args (operation parameters)
- Behavior:
  1. Verify skill is enabled and grant is not expired
  2. Verify op is in the skill's allowed_ops
  3. Dispatch to actual execution logic
- Output: execution result

> **[Uncertain]** The actual execution logic of `run_skill_action` depends on specific skill definitions. V1 provides the dispatch framework and a few example skills (e.g., repo-read, code-edit); actual tool calls may need to be delegated to Claude Code's built-in tools or other MCP Servers. The specific delegation mechanism needs to be verified during implementation.

#### F7: Per-Turn Prompt/Tool Rewriting (UserPromptSubmit Hook)

- Triggered after each user message is sent, before the model responds
- Calls PromptComposer to generate additionalContext: skill catalog summary + current active tools + authorization guidance
- Calls ToolRewriter to recalculate active_tools based on the latest skills_loaded + current_stage
- Reclaims grants that expired in the current turn
- **This hook is the core of "per-turn state-driven rewriting", corresponding to Skill-Hub's wrap_model_call**

#### F8: Session Initialization (SessionStart Hook)

- Restores or initializes session state
- Reclaims expired Grants
- Builds skill index (first time) or restores from cache
- Injects skill catalog summary and usage hints via additionalContext

#### F9: Tool Call Interception (PreToolUse Hook)

- Checks if the called tool is in the current active_tools
- If not, returns deny or ask
- If yes, returns allow

#### F10: Post-Call Processing (PostToolUse Hook)

- Records tool call audit log (with structured fields: event_type, decision, error_bucket)
- Updates skill_last_used_at timestamp

#### F11: Stage Switching -- `change_stage`

- Input: skill_id, stage_id
- Behavior: updates LoadedSkillInfo.current_stage, recalculates active_tools
- Prerequisite: skill must be enabled and have stages defined
- Purpose: same Skill exposes different tool sets per task stage (e.g., "diagnosis stage" only provides read tools, "execution stage" provides write tools)

#### F12: Skill Index Refresh -- `refresh_skills`

- Clears skill metadata cache and document cache
- Re-scans the skills/ directory and rebuilds the index
- Used for explicit refresh after skill files are updated (no hot-updates within a session by default; explicit trigger required)

### 5.2 Enhanced Features (V2 Consideration)

| # | Feature | Description |
|---|---------|-------------|
| F13 | Automatic task type classification | Automatically determine task type at the UserPromptSubmit stage and recommend candidate skills |
| F14 | Trust level management | Mark skill trust levels by source, affecting default risk assessment |
| F15 | Multi-environment policies | Support different policy configurations for dev/staging/prod environments |
| F16 | Inter-plugin governance | Manage tool conflicts and priorities between multiple plugins |
| F17 | Multi-source skill loading | Support multi-source scanning from base/team/project/user |
| F18 | Replay evaluation framework | Offline datasets, control groups, confusion matrices, miscall bucket analysis |

---

## 6 Non-Functional Requirements

### 6.1 Performance

| Metric | Requirement |
|--------|-------------|
| Hook processing latency | Single hook (SessionStart/PreToolUse/PostToolUse) processing time < 50ms |
| MCP tool response | Meta-tool (list_skills, etc.) response time < 100ms |
| Cache hit rate | In-session skill metadata cache hit rate > 95% |
| Memory usage | Plugin resident memory < 50MB |

### 6.2 Extensibility

- Core governance logic (`src/tool_governance/core/`) does not depend on Claude Code-specific APIs, facilitating future adaptation to other platforms
- Policy configuration is defined via YAML files, supporting user customization
- Skills can be written by users and placed in the skills/ directory

### 6.3 Maintainability

- Code follows Python type hint conventions (PEP 484)
- Key modules have unit test coverage
- Pydantic is used for data validation, reducing runtime type errors
- Modules communicate through explicit interfaces with low coupling

### 6.4 Security

- Skill files are treated as untrusted input: YAML uses `safe_load`, file size limits, parse failures do not affect other skills
- High-risk operations (involving shell, write, network, database) require user confirmation by default
- Audit log is append-only (SQLite table)
- Policy configuration changes require file modification, cannot be dynamically modified via MCP tools

### 6.5 Compatibility

- Python 3.11+
- Supports Windows, macOS, and Linux
- Compatible with the current stable Claude Code plugin specification

---

## 7 Interaction Flows

### 7.1 Typical Usage Flow

```
User sends task ──> [SessionStart Hook]
                        |
                        |-- Initialize/restore session state
                        |-- Reclaim expired Grants
                        +-- Inject skill catalog summary (additionalContext)
                        |
                  Claude sees the skill catalog
                        |
                        |-- Call list_skills() -> get skill list
                        |-- Call read_skill("db-ops") -> get SOP
                        |-- Call enable_skill("db-ops") -> request authorization
                        |       |
                        |       |-- [Low risk] -> auto-grant -> Grant created
                        |       +-- [High risk] -> user confirmation -> Grant created
                        |
                        |-- Call run_skill_action("db-ops", "query", {...})
                        |       |
                        |       +-- [PreToolUse Hook] check active_tools
                        |           |-- In allowlist -> allow
                        |           +-- Not in -> deny
                        |
                        +-- [PostToolUse Hook] record audit log
```

### 7.2 Authorization Denial Flow

```
Claude attempts to call an unauthorized tool
        |
  [PreToolUse Hook]
        |
  Tool not in active_tools
        |
  Return deny + additionalContext:
  "This tool requires enabling the corresponding skill first.
   Please use the read_skill and enable_skill flow."
        |
  Claude enters the correct authorization flow
```

---

## 8 Constraints

1. **Host limitation**: V1 only supports Claude Code as the host environment
2. **Language constraint**: Core logic uses Python 3.11+, depends on the LangChain framework
3. **Network constraint**: MCP Server uses stdio communication, no network port required; HTTP hook service (if used) only listens on localhost
4. **Storage constraint**: Uses the `${CLAUDE_PLUGIN_DATA}` directory to store the SQLite database and configuration
5. **No modification of Claude Code core**: The plugin can only extend behavior through the officially provided hooks, MCP, and skills mechanisms

---

## 9 Acceptance Criteria

| # | Acceptance Item | Pass Condition |
|---|-----------------|----------------|
| A1 | Plugin loading | Successfully loaded in Claude Code via plugin install command, no errors |
| A2 | Skill discovery | Model can discover all registered skills via list_skills |
| A3 | Skill reading | read_skill returns complete SOP; second call hits cache |
| A4 | Authorization flow | After enable_skill, active_tools updates correctly; model can call tools within authorized scope |
| A5 | Interception | Non-allowlisted tool calls are intercepted by PreToolUse hook and return deny |
| A6 | Authorization reclamation | After TTL expiry, Grant automatically becomes invalid; after disable_skill, tool is removed from active_tools |
| A7 | State recovery | Within the same session, SessionStart correctly restores prior state |
| A8 | Per-turn rewriting | UserPromptSubmit hook fires every turn; after enable_skill, model receives updated tool hints on the next turn |
| A9 | Stage switching | After change_stage, active_tools correctly changes to the target stage's allowed_tools |
| A10 | Skill refresh | After refresh_skills, newly added/modified skill files are discoverable |
| A11 | Audit records | Key operations have structured audit logs in SQLite, supporting funnel queries |
| A12 | Observability chain | Complete trace/session/observation chain visible in Langfuse |
| A13 | Directory structure | Plugin directory structure complies with the official specification |
| A14 | Unit tests | Core module unit test coverage > 80%, all passing |

---

## 10 Glossary

| Term | Definition |
|------|------------|
| **Skill** | A reusable combination of SOP + execution boundary, containing workflow descriptions and an allowed_tools allowlist |
| **Knowledge Plane** | The knowledge layer of a skill: SOP, applicable scenarios, step descriptions, precautions |
| **Execution Plane** | The execution layer of a skill: allowed_tools allowlist, authorization status, tool assembly |
| **skills_metadata** | Metadata index of all registered skills in a session |
| **skills_loaded** | The set of explicitly enabled skills in the current session |
| **active_tools** | The minimal tool set visible to the model in the current turn, computed as the union of allowed_tools from skills_loaded |
| **Grant** | An authorization entry created by a single enable_skill call, including scope, TTL, status, etc. |
| **Meta-tool** | The small fixed set of tools exposed to the model by the governance plugin (list_skills, read_skill, etc.), serving as the governance entry point |
| **Progressive Disclosure** | Not exposing all capabilities at once, but revealing them step by step on demand |
