# Stagewise-Tool-Gate 当前能力治理模型说明

**生成时间**: 2026-05-05  
**Git Commit**: 927a276eee303833c05d312bc7d9ce25d0109ef8  
**说明**: 本文档基于当前代码反向梳理，只描述当前有效模型，不包含旧概念或未来重构建议。

---

## 1. 当前模型一句话概括

Stagewise-Tool-Gate 实现了一个基于 Skill、Stage、Grant 的渐进式工具授权模型。

**核心机制**：Skill 定义工具集合和操作边界，Stage 控制 Skill 内部的工具可见性演进，Grant 记录授权凭证。RuntimeContext 在每个回合从持久化的 SessionState 派生出当前可用工具集 active_tools，PreToolUse hook 在工具调用前检查工具名是否在 active_tools 中，从而实现细粒度的工具准入控制。

**Skill** 是能力单元，通过 SKILL.md 的 frontmatter 声明 allowed_tools（技能级工具列表）或 stages（阶段化工具列表）。模型支持两种 Skill：
- **Staged Skill**：定义 stages 字段，每个 stage 有独立的 allowed_tools 和 allowed_next_stages，通过 change_stage 切换阶段
- **No-stage Skill**：无 stages 字段，直接使用技能级 allowed_tools

**Stage** 是 Staged Skill 内部的状态机节点，每个 Stage 定义：
- `allowed_tools`：该阶段可用的工具列表
- `allowed_next_stages`：允许转移到的下一阶段列表（空列表表示终止阶段）

**allowed_tools** 是声明式工具列表，定义在 SKILL.md 中：
- Staged Skill：每个 stage 有独立的 allowed_tools
- No-stage Skill：技能级 allowed_tools

**active_tools** 是运行时派生的工具集合，由 `build_runtime_context()` 计算：
```
active_tools = META_TOOLS ∪ (⋃ enabled_skills 的 stage_tools) − blocked_tools
```

**RuntimeContext** 是每回合构建的只读快照，包含 active_tools、enabled_skills、metadata、policy、clock。它是派生状态，不持久化。

**SessionState** 是持久化状态，包含 session_id、skills_loaded、active_grants、created_at、updated_at。active_tools 和 skills_metadata 是派生字段，不写入 SQLite。

**PreToolUse** 是工具准入检查点，在 Claude Code 调用工具前触发。它提取工具短名，检查是否在 RuntimeContext.active_tools 中，允许或拒绝调用。

**MCP meta-tools** 是治理元工具（list_skills、read_skill、enable_skill、disable_skill、grant_status、run_skill_action、change_stage、refresh_skills），始终可用，不受 Skill 授权限制。

**Hook handler** 是 stdin/stdout 子进程，处理 SessionStart、UserPromptSubmit、PreToolUse、PostToolUse 四类事件，每次加载 SessionState、构建 RuntimeContext、执行决策、持久化变更。

---

## 2. 核心概念总览

| 概念 | 当前代码名 | 所在文件 | 当前作用 | 何时产生/读取 | 是否持久化 |
|------|-----------|---------|---------|--------------|-----------|
| Skill | `SkillMetadata` | `models/skill.py` | 技能元数据，定义 allowed_tools、stages、risk_level | SkillIndexer 扫描 SKILL.md 时解析 | 否（缓存在 VersionedTTLCache） |
| SKILL.md | - | `skills/*/SKILL.md` | 技能定义文件，frontmatter 为元数据，body 为 SOP | SkillIndexer.build_index() 扫描 | 否（磁盘文件） |
| SkillContent | `SkillContent` | `models/skill.py` | 完整技能内容，包含 metadata + sop + examples | read_skill 返回 | 否（缓存在 doc_cache） |
| Stage | `StageDefinition` | `models/skill.py` | 阶段定义，包含 stage_id、allowed_tools、allowed_next_stages | 解析 SKILL.md frontmatter 的 stages 字段 | 否（属于 SkillMetadata） |
| allowed_tools | `SkillMetadata.allowed_tools` / `StageDefinition.allowed_tools` | `models/skill.py` | 声明式工具列表 | 解析 SKILL.md | 否 |
| current_stage | `LoadedSkillInfo.current_stage` | `models/state.py` | 当前所处阶段 | enable_skill 初始化，change_stage 更新 | 是（SessionState.skills_loaded） |
| Grant | `Grant` | `models/grant.py` | 授权记录，包含 grant_id、skill_id、scope、ttl、expires_at | enable_skill 创建 | 是（grants 表） |
| active_grants | `SessionState.active_grants` | `models/state.py` | skill_id -> Grant 映射 | enable_skill 写入，disable_skill 删除 | 是 |
| skills_loaded | `SessionState.skills_loaded` | `models/state.py` | skill_id -> LoadedSkillInfo 映射 | enable_skill 写入，disable_skill 删除 | 是 |
| RuntimeContext | `RuntimeContext` | `core/runtime_context.py` | 每回合派生的只读快照 | build_runtime_context() 构建 | 否 |
| active_tools | `RuntimeContext.active_tools` | `core/runtime_context.py` | 当前回合可用工具集合（权威） | build_runtime_context() 计算 | 否 |
| SessionState | `SessionState` | `models/state.py` | 会话持久化状态 | load_or_init() 加载，save() 保存 | 是（sessions 表） |
| GovernancePolicy | `GovernancePolicy` | `models/policy.py` | 全局治理策略 | load_policy() 从 YAML 加载 | 否（配置文件） |
| risk_level | `SkillMetadata.risk_level` | `models/skill.py` | 风险等级（low/medium/high） | 解析 SKILL.md | 否 |
| require_reason | `SkillPolicy.require_reason` | `models/policy.py` | 是否要求提供原因 | 策略评估时读取 | 否 |
| approval_required | `SkillPolicy.approval_required` | `models/policy.py` | 是否需要审批 | 策略评估时读取 | 否 |
| max_ttl | `SkillPolicy.max_ttl` | `models/policy.py` | 最大 TTL 上限 | cap_ttl() 时读取 | 否 |
| blocked_tools | `GovernancePolicy.blocked_tools` | `models/policy.py` | 全局禁用工具列表 | build_runtime_context() 过滤 | 否 |
| PreToolUse | `handle_pre_tool_use()` | `hook_handler.py` | 工具调用前检查 | Claude Code 调用工具时触发 | 否（事件） |
| UserPromptSubmit | `handle_user_prompt_submit()` | `hook_handler.py` | 用户提交 prompt 时触发 | 每次用户输入前 | 否（事件） |
| SessionStart | `handle_session_start()` | `hook_handler.py` | 会话启动时触发 | 会话开始时 | 否（事件） |
| PostToolUse | `handle_post_tool_use()` | `hook_handler.py` | 工具调用后记录 | 工具调用完成后 | 否（事件） |
| MCP meta-tools | `META_TOOLS` | `core/tool_rewriter.py` | 8 个治理元工具 | 始终在 active_tools 中 | 否（常量） |
| enable_skill | `enable_skill()` | `mcp_server.py` | 启用技能 | 模型调用 MCP 工具 | 否（操作） |
| disable_skill | `disable_skill()` | `mcp_server.py` | 禁用技能 | 模型调用 MCP 工具 | 否（操作） |
| change_stage | `change_stage()` | `mcp_server.py` | 切换阶段 | 模型调用 MCP 工具 | 否（操作） |
| list_skills | `list_skills()` | `mcp_server.py` | 列出所有技能 | 模型调用 MCP 工具 | 否（操作） |
| read_skill | `read_skill()` | `mcp_server.py` | 读取技能详情 | 模型调用 MCP 工具 | 否（操作） |
| refresh_skills | `refresh_skills()` | `mcp_server.py` | 刷新技能索引 | 模型调用 MCP 工具 | 否（操作） |
| audit_log | `audit_log` 表 | `storage/sqlite_store.py` | 审计日志 | append_audit() 写入 | 是（SQLite） |
| sessions | `sessions` 表 | `storage/sqlite_store.py` | 会话状态表 | save_session() 写入 | 是（SQLite） |
| grants | `grants` 表 | `storage/sqlite_store.py` | 授权记录表 | insert_grant() 写入 | 是（SQLite） |

---


## 3. Skill / Stage / Tool 当前模型

### 3.1 Skill 是什么

Skill 是能力单元，通过 `SKILL.md` 文件定义。每个 Skill 包含：

**SkillMetadata**（元数据）：
- `skill_id`：唯一标识符
- `name`：显示名称
- `description`：功能描述
- `risk_level`：风险等级（low/medium/high）
- `allowed_tools`：技能级工具列表（no-stage skill 使用）
- `allowed_ops`：允许的操作列表
- `stages`：阶段定义列表（staged skill 使用）
- `initial_stage`：初始阶段（staged skill 的入口阶段）
- `default_ttl`：默认授权时长
- `source_path`：SKILL.md 文件路径
- `version`：版本号

**SkillContent**（完整内容）：
- `metadata`：SkillMetadata 对象
- `sop`：标准操作流程（SKILL.md 的 body 部分）
- `examples`：使用示例列表

**SKILL.md 结构**：
```yaml
---
skill_id: example-skill
name: Example Skill
description: Skill description
risk_level: medium
allowed_tools:
  - tool_a
  - tool_b
stages:
  - stage_id: stage1
    allowed_tools: [tool_a]
    allowed_next_stages: [stage2]
  - stage_id: stage2
    allowed_tools: [tool_b]
    allowed_next_stages: []
initial_stage: stage1
---

# Skill SOP

This is the standard operating procedure...
```

**read_skill 如何工作**：
- 模型调用 `read_skill(skill_id)` MCP 工具
- SkillIndexer 从 doc_cache 或磁盘读取 SKILL.md
- 解析 frontmatter 为 SkillMetadata，body 为 sop
- 返回 SkillContent 对象，包含完整元数据和 SOP
- 模型获得技能的完整说明，用于理解工作流程

---

### 3.2 Stage 是什么

Stage 是 Staged Skill 内部的状态机节点，用于控制工具可见性的渐进演进。

**StageDefinition**（阶段定义）：
- `stage_id`：阶段唯一标识符
- `description`：阶段描述
- `allowed_tools`：该阶段可用的工具列表
- `allowed_next_stages`：允许转移到的下一阶段列表（空列表 = 终止阶段）

**current_stage 存储位置**：
- `LoadedSkillInfo.current_stage`（SessionState.skills_loaded 中）
- 持久化字段，跨 hook 进程重启保持
- enable_skill 时初始化为 initial_stage 或第一个 stage
- change_stage 时更新

**change_stage 如何工作**：
1. 检查 skill 是否已启用
2. 检查 skill 是否有 stages（no-stage skill 返回错误）
3. 检查目标 stage 是否存在
4. 检查 current_stage 是否已初始化
5. 检查当前 stage 的 allowed_next_stages 是否包含目标 stage
6. 如果 allowed_next_stages 为空，拒绝转移（终止阶段）
7. 通过检查后，更新 current_stage、stage_entered_at、stage_history、exited_stages
8. 重新构建 RuntimeContext，active_tools 自动更新为新阶段的工具集
9. 持久化 SessionState
10. 记录 audit 事件（stage.transition.allow 或 stage.transition.deny）

**Stage 如何影响 active_tools**：
- `ToolRewriter.get_stage_tools(meta, current_stage)` 根据 current_stage 返回对应的 allowed_tools
- Staged skill：返回 current_stage 对应的 stage.allowed_tools
- No-stage skill：返回 skill-level allowed_tools
- current_stage 为 None 且有 stages：返回第一个 stage 的 allowed_tools
- current_stage 不匹配任何 stage：返回空列表（安全降级）

**allowed_next_stages 支持**：
- 当前代码完整支持 allowed_next_stages
- change_stage 强制检查转移合法性
- 空列表表示终止阶段，阻止所有转移
- 非法转移返回错误，不修改状态

---

### 3.3 Tool 是什么

Tool 是可调用的操作单元，在代码中以字符串名称表示。

**工具名表示**：
- MCP meta-tools：完整名称，如 `mcp__tool-governance__list_skills`
- Skill 业务工具：短名称，如 `yuque_search`、`Read`、`Edit`

**MCP meta-tools 与业务工具的命名空间**：
- 同一命名空间，都在 active_tools 中
- META_TOOLS 是 frozenset，包含 8 个完整 MCP 工具名
- 业务工具名来自 SKILL.md 的 allowed_tools，通常是短名

**allowed_tools 中的工具名与 PreToolUse 的对应**：
- SKILL.md 中写短名：`yuque_search`
- PreToolUse 收到的 tool_name 可能是完整名或短名
- `_extract_tool_short_name()` 提取短名：`mcp__tool-governance__list_skills` → `list_skills`
- PreToolUse 同时检查短名和完整名是否在 active_tools 中

**_extract_tool_short_name() 逻辑**：
```python
def _extract_tool_short_name(tool_name: str) -> str:
    parts = tool_name.split("__")
    return parts[-1] if len(parts) >= 3 else tool_name
```
- 如果工具名包含至少 3 个 `__` 分段，返回最后一段
- 否则返回原始工具名

---

## 4. allowed_tools 与 active_tools 的当前关系

### 4.1 allowed_tools

**定义位置**：
- Skill-level：`SkillMetadata.allowed_tools`（no-stage skill 使用）
- Stage-level：`StageDefinition.allowed_tools`（staged skill 使用）

**Skill-level 与 Stage-level 的关系**：
- **Staged skill**：skill-level allowed_tools 被忽略，使用 stage-level allowed_tools
- **No-stage skill**：只有 skill-level allowed_tools，没有 stages 字段
- 当 skill 有 stages 时，stage-level allowed_tools 完全覆盖 skill-level

**读取 allowed_tools 的关键函数**：
- `ToolRewriter.get_stage_tools(skill_meta, current_stage)`
  - 无 stages：返回 `skill_meta.allowed_tools`
  - 有 stages，current_stage 为 None：返回第一个 stage 的 allowed_tools
  - 有 stages，current_stage 匹配：返回对应 stage 的 allowed_tools
  - 有 stages，current_stage 不匹配：返回空列表

---

### 4.2 active_tools

**生成位置**：
- `RuntimeContext.active_tools`（权威来源）
- 由 `build_runtime_context()` 计算

**build_runtime_context() 计算逻辑**：
```python
def build_runtime_context(
    state: SessionState,
    metadata: Mapping[str, SkillMetadata] | None = None,
    blocked_tools: Iterable[str] = (),
    clock: datetime | None = None,
) -> RuntimeContext:
    tools = set(META_TOOLS)  # 1. 添加元工具
    
    for skill_id, loaded in state.skills_loaded.items():
        meta = metadata.get(skill_id)
        if meta is None:
            continue  # 安全降级：未知 skill 贡献 0 工具
        
        grant = state.active_grants.get(skill_id)
        if grant is None or (grant.expires_at and grant.expires_at < clock):
            continue  # 无授权或已过期，贡献 0 工具
        
        # 2. 添加 skill 的 stage_tools
        tools.update(ToolRewriter.get_stage_tools(meta, loaded.current_stage))
    
    # 3. 减去 blocked_tools
    tools -= frozenset(blocked_tools)
    
    return RuntimeContext(
        active_tools=tuple(sorted(tools)),
        ...
    )
```

**权威来源**：
- `RuntimeContext.active_tools` 是权威
- `SessionState.active_tools` 是兼容字段，通过 `sync_from_runtime()` 镜像
- `SessionState.active_tools` 不持久化（DERIVED_FIELDS 排除）

**兼容字段与 adapter**：
- `SessionState.active_tools` 仍存在，但标记为派生字段
- `to_persisted_dict()` 排除 active_tools，不写入 SQLite
- `sync_from_runtime(runtime_active_tools)` 将 RuntimeContext.active_tools 镜像到 SessionState.active_tools
- 未迁移的代码仍可读取 `state.active_tools`，但值仅在当前回合有效

**active_tools 是否持久化**：
- 否。active_tools 是派生字段，每回合重新计算
- SessionState.to_persisted_dict() 排除 active_tools
- 下次加载 SessionState 时，active_tools 为空列表，需重新构建 RuntimeContext

---

### 4.3 二者关系

**公式**：
```
active_tools = META_TOOLS ∪ (⋃ enabled_skills 的 stage_tools) − blocked_tools

其中：
- META_TOOLS = 8 个 MCP 元工具（始终可用）
- enabled_skills = skills_loaded 中有有效 grant 的 skill
- stage_tools = ToolRewriter.get_stage_tools(meta, current_stage)
- blocked_tools = GovernancePolicy.blocked_tools（全局禁用列表）
```

**流程图**：
```
SKILL.md (allowed_tools / stages)
    ↓ 解析
SkillMetadata (allowed_tools / stages)
    ↓ 缓存
SkillIndexer._metadata_cache
    ↓ 读取
build_runtime_context()
    ↓ 计算
    1. tools = META_TOOLS
    2. for each enabled skill with valid grant:
         tools += get_stage_tools(meta, current_stage)
    3. tools -= blocked_tools
    ↓ 输出
RuntimeContext.active_tools (sorted tuple)
    ↓ 镜像
SessionState.active_tools (list, 不持久化)
    ↓ 检查
PreToolUse: tool_name in active_tools?
```

---

## 5. RuntimeContext 与 SessionState 的分工

### 5.1 SessionState 当前负责什么

**SessionState** 是持久化状态容器，负责跨回合、跨进程的状态保持。

**当前字段**：
- `session_id`：会话唯一标识符（持久化）
- `skills_loaded`：dict[str, LoadedSkillInfo]，已启用技能列表（持久化）
- `active_grants`：dict[str, Grant]，skill_id -> Grant 映射（持久化）
- `created_at`：会话创建时间（持久化）
- `updated_at`：最后更新时间（持久化）
- `active_tools`：list[str]，派生字段，不持久化
- `skills_metadata`：dict[str, SkillMetadata]，派生字段，不持久化

**持久化字段**：
- `session_id`、`skills_loaded`、`active_grants`、`created_at`、`updated_at`
- 这些字段通过 `to_persisted_dict()` 写入 SQLite sessions 表

**非持久化字段**：
- `active_tools`：派生字段，每回合从 RuntimeContext 镜像
- `skills_metadata`：派生字段，权威来源是 SkillIndexer

**to_persisted_dict() 如何工作**：
```python
DERIVED_FIELDS: ClassVar[frozenset[str]] = frozenset({"active_tools", "skills_metadata"})

def to_persisted_dict(self, mode: str = "json") -> dict[str, Any]:
    return self.model_dump(mode=mode, exclude=self.DERIVED_FIELDS)
```
- 排除 `active_tools` 和 `skills_metadata`
- 只序列化持久化字段
- StateManager.save() 调用此方法获取持久化 payload

**SQLite 中保存的内容**：
- sessions 表：session_id, state_json, created_at, updated_at
- state_json 包含：session_id, skills_loaded, active_grants, created_at, updated_at
- state_json 不包含：active_tools, skills_metadata

---

### 5.2 RuntimeContext 当前负责什么

**RuntimeContext** 是每回合派生的只读快照，负责提供当前回合的运行时视图。

**当前字段**：
- `active_tools`：tuple[str, ...]，当前可用工具集合（排序后的元组）
- `enabled_skills`：tuple[EnabledSkillView, ...]，已启用技能视图
- `all_skills_metadata`：Mapping[str, SkillMetadata]，所有技能元数据
- `policy`：PolicySnapshot，策略快照（包含 blocked_tools）
- `clock`：datetime，构建时间戳

**frozen / immutable**：
- 是。RuntimeContext 是 `@dataclass(frozen=True)`
- 所有字段不可变
- active_tools 是 tuple（不可变），不是 list

**何时构建**：
- 每个 hook 事件处理时构建一次
- SessionStart、UserPromptSubmit、PreToolUse、PostToolUse 都调用 `_build_runtime_ctx()`
- MCP 工具调用时也构建（enable_skill、disable_skill、change_stage 等）

**是否持久化**：
- 否。RuntimeContext 是临时对象，不写入 SQLite
- 每回合重新构建

**与 SessionState 的关系**：
- RuntimeContext 从 SessionState 派生
- SessionState 提供持久化输入（skills_loaded、active_grants）
- RuntimeContext 提供运行时输出（active_tools、enabled_skills）
- SessionState.sync_from_runtime() 将 RuntimeContext.active_tools 镜像回 SessionState.active_tools

---

### 5.3 当前入口点如何使用 RuntimeContext

#### hook_handler

**四个 hook 事件的统一模式**：
```python
def handle_xxx(input_data):
    rt = _get_runtime()
    session_id = discover_session_id(input_data)
    
    # 1. Load persisted state
    state = rt.state_manager.load_or_init(session_id)
    
    # 2. Derive runtime context
    ctx = _build_runtime_ctx(rt, state)
    
    # 3. Execute (read or mutate state)
    # ...
    
    # 4. Persist durable fields (if mutated)
    rt.state_manager.save(state)
```

**_build_runtime_ctx() 实现**：
```python
def _build_runtime_ctx(rt: GovernanceRuntime, state: SessionState) -> RuntimeContext:
    metadata = rt.indexer.current_index() or state.skills_metadata
    return build_runtime_context(
        state,
        metadata=metadata,
        blocked_tools=rt.tool_rewriter.blocked_tools,
    )
```

**PreToolUse 使用 RuntimeContext**：
- 构建 RuntimeContext
- 检查 `tool_name in ctx.active_tools_set()`
- 如果拒绝，调用 `_classify_deny_bucket(tool_name, ctx)` 分类错误

**PostToolUse 使用 RuntimeContext**：
- 构建 RuntimeContext
- 遍历 `ctx.enabled_skills` 查找拥有 tool_name 的 skill
- 更新 `state.skills_loaded[skill_id].last_used_at`

---

#### mcp_server

**MCP 工具的统一模式**：
```python
async def mcp_tool():
    rt = _get_runtime()
    sid = _session_id()
    
    # Step 1: Load persisted state
    state = rt.state_manager.load_or_init(sid)
    
    # Step 2: Derive runtime context
    ctx = _build_runtime_ctx(rt, state)
    
    # Step 3: Execute (mutate state if needed)
    # ...
    state.sync_from_runtime(ctx.active_tools)
    
    # Step 4: Save persisted state
    rt.state_manager.save(state)
```

**enable_skill 使用 RuntimeContext**：
- 修改 skills_loaded 和 active_grants 后
- 重新构建 RuntimeContext 获取新的 active_tools
- 调用 `state.sync_from_runtime(ctx.active_tools)` 镜像
- 返回 `{"granted": True, "allowed_tools": list(ctx.active_tools)}`

**change_stage 使用 RuntimeContext**：
- 修改 current_stage 后
- 重新构建 RuntimeContext 获取新的 active_tools
- 调用 `state.sync_from_runtime(ctx.active_tools)` 镜像
- 返回 `{"changed": True, "new_active_tools": list(ctx.active_tools)}`

**list_skills 使用 RuntimeContext**：
- 构建 RuntimeContext 获取 all_skills_metadata
- 遍历 `ctx.all_skills_metadata` 返回技能列表
- 检查 `skill_id in state.skills_loaded` 判断是否已启用

---

#### LangChain / tools entrypoint

当前项目有 `src/tool_governance/tools/langchain_tools.py`，但主要入口是 hook_handler 和 mcp_server。

LangChain 工具入口已迁移到使用 RuntimeContext 模式（如果使用）。

---

#### prompt composer / tool rewriter

**PromptComposer**：
- `compose_skill_catalog(ctx: RuntimeContext)` 接收 RuntimeContext
- 遍历 `ctx.enabled_skills` 生成技能目录
- SessionStart 和 UserPromptSubmit 调用

**ToolRewriter**：
- `recompute_active_tools(state, indexer)` 已标记为 DEPRECATED
- 新代码使用 `compute_active_tools(ctx: RuntimeContext)`
- `compute_active_tools()` 直接返回 `list(ctx.active_tools)`

---

## 6. 授权链路：从发现 Skill 到工具调用

### 6.1 Skill discovery

**refresh_skills**：
- 模型调用 `refresh_skills()` MCP 工具
- SkillIndexer.refresh() 清空缓存，重新扫描 skills/ 目录
- 返回发现的技能数量

**list_skills**：
- 模型调用 `list_skills()` MCP 工具
- 从 RuntimeContext.all_skills_metadata 读取所有技能
- 返回技能列表：skill_id, name, description, risk_level, is_enabled

**read_skill**：
- 模型调用 `read_skill(skill_id)` MCP 工具
- SkillIndexer.read_skill() 从 doc_cache 或磁盘读取 SKILL.md
- 解析 frontmatter 和 body
- 返回 SkillContent：metadata + sop + examples

**SkillIndexer 当前行为**：
- 扫描 skills/ 目录一级子目录
- 每个子目录查找 SKILL.md
- 解析 frontmatter 为 SkillMetadata
- 缓存到 VersionedTTLCache（metadata_cache 和 doc_cache）
- current_index() 返回当前缓存的 metadata 字典

---

### 6.2 enable_skill

**完整流程**：

1. **Policy evaluation**：
   - PolicyEngine.evaluate(skill_id, skill_meta, state, reason)
   - 检查 blocked_tools（全局禁用列表）
   - 检查 skill-specific policy（SkillPolicy）
   - 检查 risk_level 对应的 default_risk_thresholds
   - 返回 PolicyDecision：allowed, decision, reason

2. **risk_level 处理**：
   - low：默认 "auto"，自动授权
   - medium：默认 "reason"，需要提供 reason
   - high：默认 "approval"，需要审批（当前未强制）

3. **require_reason 检查**：
   - 如果 SkillPolicy.require_reason = True 且 reason 为空，拒绝
   - 返回 `{"allowed": False, "decision": "reason_required"}`

4. **approval_required 检查**：
   - 如果 SkillPolicy.approval_required = True，拒绝
   - 返回 `{"allowed": False, "decision": "approval_required"}`
   - 当前代码不强制等待审批，只返回错误

5. **TTL / max_ttl 处理**：
   - PolicyEngine.cap_ttl(skill_id, requested_ttl)
   - 读取 SkillPolicy.max_ttl 或 GovernancePolicy.default_ttl
   - 返回 min(requested_ttl, max_ttl)

6. **Grant 创建**：
   - GrantManager.create_grant() 创建 Grant 对象
   - grant_id = uuid4()
   - expires_at = now + timedelta(seconds=ttl)
   - status = "active"
   - granted_by = "auto" / "user" / "policy"
   - 写入 grants 表

7. **active_grants 写入**：
   - state.active_grants[skill_id] = grant
   - 覆盖旧 grant（如果存在）

8. **skills_loaded 写入**：
   - LoadedSkillInfo(skill_id, version, current_stage, ...)
   - 如果 skill 有 stages，初始化 current_stage = initial_stage 或第一个 stage
   - 如果 skill 无 stages，current_stage = None
   - 初始化 stage_entered_at、stage_history、exited_stages
   - state.skills_loaded[skill_id] = loaded_info

9. **Audit 记录**：
   - store.append_audit(session_id, "skill.enable", skill_id, decision="granted")
   - 记录 scope、ttl 到 detail

---

### 6.3 change_stage

**完整流程**：

1. **当前 stage 验证**：
   - 检查 skill 是否已启用（skill_id in state.skills_loaded）
   - 检查 skill 是否有 stages（meta.stages 非空）
   - 检查 current_stage 是否已初始化（不为 None）

2. **目标 stage 验证**：
   - 检查 stage_id 是否在 meta.stages 中
   - 如果不存在，返回错误 "stage_not_found"

3. **allowed_next_stages 检查**：
   - 读取 current_stage_def.allowed_next_stages
   - 如果为空列表，拒绝转移（终止阶段）
   - 如果 stage_id 不在 allowed_next_stages 中，拒绝转移
   - 返回错误 "stage_transition_not_allowed"

4. **Stage 切换如何影响 active_tools**：
   - 更新 loaded_info.current_stage = stage_id
   - 更新 loaded_info.stage_entered_at = now
   - 追加 StageTransitionRecord 到 stage_history
   - 追加 current_stage_id 到 exited_stages
   - 重新构建 RuntimeContext
   - build_runtime_context() 调用 get_stage_tools(meta, new_stage)
   - active_tools 自动更新为新阶段的工具集

5. **Audit 如何记录**：
   - 成功：`store.append_audit(session_id, "stage.transition.allow", skill_id, detail={"from_stage": ..., "to_stage": ...})`
   - 失败：`store.append_audit(session_id, "stage.transition.deny", skill_id, detail={"from_stage": ..., "to_stage": ..., "error_bucket": ...})`

---

### 6.4 PreToolUse

**完整流程**：

1. **输入**：
   - `input_data`：包含 session_id, tool_name, tool_input
   - tool_name：完整工具名或短名

2. **提取 tool name**：
   - `_extract_tool_short_name(tool_name)` 提取短名
   - 例如：`mcp__tool-governance__list_skills` → `list_skills`

3. **Meta-tools 快速通道**：
   - 检查 `short_name in _META_SHORT_NAMES` 或 `tool_name in META_TOOLS`
   - 如果是元工具，直接返回 allow，不检查 active_tools

4. **构建 RuntimeContext**：
   - 加载 SessionState
   - 调用 `_build_runtime_ctx(rt, state)` 构建 RuntimeContext
   - 获取 ctx.active_tools

5. **检查 tool 是否可用**：
   - 检查 `short_name in ctx.active_tools_set()` 或 `tool_name in ctx.active_tools_set()`
   - 如果在，返回 allow
   - 如果不在，进入 deny 流程

6. **Allow 返回结构**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow"
  }
}
```

7. **Deny 返回结构**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Tool 'xxx' is not in active_tools. Please use read_skill and enable_skill...",
    "additionalContext": "To use this tool, first discover available skills with list_skills..."
  }
}
```

8. **Deny 的错误分类**：
   - `_classify_deny_bucket(tool_name, runtime_ctx)` 分类错误
   - **wrong_skill_tool**：工具属于某个已索引的 skill，但该 skill 未启用
   - **tool_not_available**：其他所有情况（工具未知、被 blocked、不在当前 stage）

**错误分类逻辑**：
```python
def _classify_deny_bucket(tool_name: str, runtime_ctx: RuntimeContext) -> str:
    short_name = _extract_tool_short_name(tool_name)
    enabled_ids = runtime_ctx.enabled_skill_ids()
    
    if not enabled_ids:
        return "tool_not_available"  # 没有启用任何 skill
    
    # 检查工具是否在已启用 skill 的 allowed_tools 中
    for sv in runtime_ctx.enabled_skills:
        if short_name in sv.metadata.allowed_tools:
            return "tool_not_available"  # 在已启用 skill 中，但被 stage/blocked 过滤
        for stage in sv.metadata.stages or []:
            if short_name in stage.allowed_tools:
                return "tool_not_available"
    
    # 检查工具是否在其他未启用 skill 的 allowed_tools 中
    for skill_id, meta in runtime_ctx.all_skills_metadata.items():
        if skill_id in enabled_ids:
            continue
        if short_name in meta.allowed_tools:
            return "wrong_skill_tool"  # 工具属于未启用的 skill
        for stage in meta.stages or []:
            if short_name in stage.allowed_tools:
                return "wrong_skill_tool"
    
    return "tool_not_available"  # 工具完全未知
```

---

## 7. blocked_tools 当前模型

### 配置位置

**GovernancePolicy.blocked_tools**：
- 定义在 `models/policy.py`
- 类型：`list[str]`
- 从 `config/default_policy.yaml` 加载

**示例配置**：
```yaml
blocked_tools:
  - dangerous_tool
  - deprecated_tool
```

### 当前字段名

- `GovernancePolicy.blocked_tools`：策略配置中的字段
- `ToolRewriter.blocked_tools`：ToolRewriter 实例的属性（frozenset）
- `PolicySnapshot.blocked_tools`：RuntimeContext 中的策略快照（frozenset）

### 级别

**全局 policy 级别**：
- blocked_tools 是全局配置，不是 skill-specific 或 stage-specific
- 所有 skill 的所有 stage 都受 blocked_tools 约束

### 如何参与 active_tools 计算

**在 build_runtime_context() 中过滤**：
```python
def build_runtime_context(..., blocked_tools: Iterable[str] = ()) -> RuntimeContext:
    tools = set(META_TOOLS)
    
    for skill_id, loaded in state.skills_loaded.items():
        # ... 添加 skill 的 stage_tools
        tools.update(ToolRewriter.get_stage_tools(meta, loaded.current_stage))
    
    # 最后减去 blocked_tools
    tools -= frozenset(blocked_tools)
    
    return RuntimeContext(active_tools=tuple(sorted(tools)), ...)
```

**过滤时机**：
- PreToolUse 之前，在 build_runtime_context() 中过滤
- blocked_tools 中的工具永远不会出现在 active_tools 中

### 当前系统如何表现

**如果一个工具被 blocked**：
1. 即使 skill 的 allowed_tools 包含该工具
2. 即使 skill 已启用且有有效 grant
3. 该工具也不会出现在 active_tools 中
4. PreToolUse 会拒绝该工具调用
5. 错误分类为 "tool_not_available"（不是专门的 blocked 错误）

### 当前 tests/examples 覆盖

**simulator-demo**：
- 未专门测试 blocked_tools（可以添加）

**legacy examples**：
- `02-doc-edit-staged` 演示 blocked_tools
- 配置 `blocked_tools: [run_command]` 阻止 shell 执行

### 是否有专门的 blocked 错误类型

**否**。当前代码没有专门的 "tool_blocked" 错误类型。

被 blocked 的工具在 PreToolUse 中被归类为 "tool_not_available"，与其他不可用工具（未知工具、不在当前 stage）使用相同的错误类型。

**原因**：
- blocked_tools 在 build_runtime_context() 中过滤
- PreToolUse 只看到过滤后的 active_tools
- PreToolUse 无法区分工具是被 blocked 还是其他原因不可用

**如果需要区分**：
- 需要在 PreToolUse 中额外检查 `tool_name in runtime_ctx.policy.blocked_tools`
- 返回专门的 "tool_blocked" 错误类型
- 当前代码未实现此功能

---

## 8. 审计与可观测性模型

### SQLite audit_log

**表结构**：
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    skill_id TEXT,
    tool_name TEXT,
    decision TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);
```

**字段说明**：
- `event_type`：事件类型（skill.enable, skill.disable, tool.call, stage.transition.allow, stage.transition.deny, grant.expire, prompt.submit）
- `decision`：决策结果（granted, revoked, allow, deny, expired）
- `detail`：JSON 字符串，包含额外信息（error_bucket, from_stage, to_stage, scope, ttl）

### sessions 表

**表结构**：
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**state_json 内容**：
- 持久化字段：session_id, skills_loaded, active_grants, created_at, updated_at
- 不包含：active_tools, skills_metadata

### simulator-demo 的 events.jsonl / audit_summary.md / metrics.json

**当前保留**：
- `examples/simulator-demo/` 包含完整的 simulator 和 scenario
- 每个 scenario 运行后生成：
  - `events.jsonl`：事件流水日志
  - `audit_summary.md`：审计摘要报告
  - `metrics.json`：指标统计

**events.jsonl 格式**：
```json
{"timestamp": "...", "event": "SessionStart", "session_id": "..."}
{"timestamp": "...", "event": "MCP", "tool": "list_skills", "result": {...}}
{"timestamp": "...", "event": "Hook", "hook": "PreToolUse", "tool": "...", "decision": "allow"}
```

### 治理决策事件 vs session lifecycle / bookkeeping

**治理决策事件**（记录到 audit_log）：
- `skill.enable`：启用技能
- `skill.disable`：禁用技能
- `tool.call`：工具调用（allow/deny/error）
- `stage.transition.allow`：阶段转移成功
- `stage.transition.deny`：阶段转移失败
- `grant.expire`：授权过期

**Session lifecycle / bookkeeping**（记录到 audit_log）：
- `prompt.submit`：用户提交 prompt
- `skill.list`：列出技能
- `skill.read`：读取技能详情

**区分标准**：
- 治理决策事件：影响授权状态、工具可见性、阶段转移
- Lifecycle 事件：不改变状态，只记录操作

### 当前 demo 或代码如何验证事件覆盖

**simulator-demo**：
- 三个 scenario 覆盖不同事件组合
- Scenario 01：skill.enable, tool.call (allow/deny), skill.list, skill.read
- Scenario 02：stage.transition.allow, stage.transition.deny
- Scenario 03：grant.expire, skill.disable

**验证方式**：
- 运行 `./run_simulator.sh`
- 检查 `.scenario-XX-data/governance.db` 的 audit_log 表
- 检查 `.scenario-XX-data/events.jsonl`
- 运行 `verify_stage_first.py` 验证事件覆盖

---

## 9. 当前核心数据流图

### 9.1 Skill indexing flow

```
skills/*/SKILL.md (磁盘文件)
    ↓ 扫描
SkillIndexer.build_index()
    ↓ 解析 frontmatter
_parse_frontmatter() → (dict, body)
    ↓ 构建
_build_metadata() → SkillMetadata
    ↓ 缓存
VersionedTTLCache._metadata_cache
    ↓ 读取
SkillIndexer.current_index() → dict[skill_id, SkillMetadata]
    ↓ 传递
build_runtime_context(metadata=...)
    ↓ 使用
RuntimeContext.all_skills_metadata
```

**关键点**：
- SKILL.md 是唯一真实来源
- SkillIndexer 负责扫描和解析
- VersionedTTLCache 提供性能层（TTL=300s）
- RuntimeContext 每回合从 indexer 读取最新 metadata

---

### 9.2 enable_skill flow

```
模型调用 enable_skill(skill_id, reason, scope, ttl)
    ↓ MCP 工具
mcp_server.enable_skill()
    ↓ 1. 加载状态
StateManager.load_or_init(session_id) → SessionState
    ↓ 2. 策略评估
PolicyEngine.evaluate(skill_id, meta, state, reason)
    ↓ 检查
    - blocked_tools（全局禁用）
    - SkillPolicy（技能特定策略）
    - risk_level thresholds（风险等级）
    ↓ 返回
PolicyDecision(allowed, decision, reason)
    ↓ 3. 创建授权
GrantManager.create_grant() → Grant
    ↓ 写入
SQLiteStore.insert_grant() → grants 表
    ↓ 更新状态
state.active_grants[skill_id] = grant
state.skills_loaded[skill_id] = LoadedSkillInfo(
    current_stage = initial_stage or stages[0].stage_id,
    stage_entered_at = now,
    ...
)
    ↓ 4. 重建运行时
build_runtime_context(state, metadata, blocked_tools)
    ↓ 计算
active_tools = META_TOOLS ∪ stage_tools − blocked_tools
    ↓ 镜像
state.sync_from_runtime(ctx.active_tools)
    ↓ 5. 持久化
StateManager.save(state) → sessions 表
    ↓ 审计
SQLiteStore.append_audit("skill.enable", decision="granted")
    ↓ 返回
{"granted": True, "allowed_tools": [...]}
```

---

### 9.3 active_tools computation flow

```
SessionState (持久化输入)
    - skills_loaded: {skill_id: LoadedSkillInfo}
    - active_grants: {skill_id: Grant}
    ↓ 传递
build_runtime_context(state, metadata, blocked_tools, clock)
    ↓ 初始化
tools = set(META_TOOLS)
    ↓ 遍历 skills_loaded
for skill_id, loaded in state.skills_loaded.items():
    ↓ 查找元数据
    meta = metadata.get(skill_id)
    if meta is None: continue  # 安全降级
    
    ↓ 检查授权
    grant = state.active_grants.get(skill_id)
    if grant is None: continue  # 无授权
    if grant.expires_at < clock: continue  # 已过期
    
    ↓ 获取阶段工具
    stage_tools = ToolRewriter.get_stage_tools(meta, loaded.current_stage)
        ↓ 分支
        - 无 stages: return meta.allowed_tools
        - 有 stages, current_stage=None: return stages[0].allowed_tools
        - 有 stages, current_stage 匹配: return stage.allowed_tools
        - 有 stages, current_stage 不匹配: return []
    
    ↓ 合并
    tools.update(stage_tools)

    ↓ 过滤
tools -= frozenset(blocked_tools)
    ↓ 排序
active_tools = tuple(sorted(tools))
    ↓ 输出
RuntimeContext(active_tools=active_tools, ...)
```

**关键决策点**：
1. **Grant 有效性**：无 grant 或已过期 → 贡献 0 工具
2. **Metadata 缺失**：skill_id 在 skills_loaded 但 metadata 中无 → 贡献 0 工具（安全降级）
3. **Stage 匹配**：current_stage 不匹配任何 stage → 贡献 0 工具
4. **Blocked 过滤**：最后统一减去 blocked_tools

---

### 9.4 PreToolUse authorization flow

```
Claude Code 调用工具
    ↓ Hook 事件
handle_pre_tool_use(input_data)
    ↓ 提取
tool_name = input_data["tool_name"]
short_name = _extract_tool_short_name(tool_name)
    ↓ 快速通道
if short_name in _META_SHORT_NAMES:
    return {"permissionDecision": "allow"}
    ↓ 1. 加载状态
state = StateManager.load_or_init(session_id)
    ↓ 2. 构建运行时
ctx = build_runtime_context(state, metadata, blocked_tools)
    ↓ 3. 检查工具
if short_name in ctx.active_tools_set() or tool_name in ctx.active_tools_set():
    ↓ 允许
    append_audit("tool.call", decision="allow")
    return {"permissionDecision": "allow"}
else:
    ↓ 拒绝
    bucket = _classify_deny_bucket(tool_name, ctx)
        ↓ 分类
        - wrong_skill_tool: 工具属于未启用的 skill
        - tool_not_available: 其他所有情况
    ↓ 审计
    append_audit("tool.call", decision="deny", detail={"error_bucket": bucket})
    ↓ 返回
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": "Tool 'xxx' is not in active_tools...",
        "additionalContext": "To use this tool, first discover..."
    }
```

---

### 9.5 simulator-demo flow

```
用户运行 ./run_simulator.sh
    ↓ 启动
simulator/agent.py (主进程)
    ↓ 创建子进程
    - hook_subprocess (tg-hook stdin/stdout)
    - mcp_subprocess (tg-mcp stdin/stdout)
    ↓ 共享状态
    - SQLite governance.db (WAL 模式)
    - sessions 表、grants 表、audit_log 表
    ↓ 执行 scenario
scenarios/scenario_XX.py
    ↓ 发送事件
    1. SessionStart → hook_subprocess
    2. list_skills → mcp_subprocess
    3. read_skill → mcp_subprocess
    4. enable_skill → mcp_subprocess
    5. PreToolUse → hook_subprocess
    6. change_stage → mcp_subprocess
    7. PostToolUse → hook_subprocess
    ↓ 记录
    - events.jsonl (事件流水)
    - governance.db (持久化状态 + 审计)
    ↓ 生成报告
    - audit_summary.md (审计摘要)
    - metrics.json (指标统计)
    ↓ 验证
verify_stage_first.py
    ↓ 检查
    - Stage-first metadata 存在
    - Stage transition governance 生效
    - Terminal stage 阻止转移
    - Audit events 完整
```

**关键隔离边界**：
- Agent 主进程 ↔ Hook 子进程：stdin/stdout JSON
- Agent 主进程 ↔ MCP 子进程：stdin/stdout JSON
- Hook 子进程 ↔ MCP 子进程：通过 SQLite 共享状态（不直接通信）

---

## 10. 当前模型如何支撑 demo 展示

### examples/README.md 的角色

**定位**：
- 交付演示样例的总入口
- 介绍 canonical demo（simulator-demo）和 legacy examples（01-03）
- 提供 Capability Coverage Matrix 和功能/接口覆盖矩阵

**内容**：
- Canonical Stage-first Demo：`simulator-demo/`
- Legacy Examples（已废弃）：`01-knowledge-link/`, `02-doc-edit-staged/`, `03-lifecycle-and-risk/`
- 环境要求、启动方式、常见问题

**说明**：
- Legacy examples 不演示 Stage-first governance
- 新的 Stage-first 验收以 `simulator-demo/` 为准

---

### simulator-demo 的角色

**定位**：
- Stage-first Skill Governance 的 canonical acceptance target
- 通过 Python 子进程模拟完整的 Claude Code 调用链路
- 演示 Stage-first metadata、Stage transition governance、Terminal stages

**核心价值**：
1. **子进程隔离**：真实模拟 Claude Code 的 hook/MCP 子进程边界
2. **协议边界**：stdin/stdout JSON 通信，验证协议正确性
3. **SQLite 共享状态**：hook 和 MCP 子进程通过 SQLite 共享状态
4. **完整审计链**：所有事件记录到 audit_log 和 events.jsonl
5. **Stage-first metadata**：演示 initial_stage、stages、allowed_next_stages
6. **Stage transition governance**：演示合法/非法转移、终止阶段

---

### 三个 scenario 分别展示什么

#### Scenario 01: Discovery

**主题**：Skill discovery, Stage-first metadata (staged vs no-stage skills)

**演示内容**：
- `list_skills`：发现 2 个技能（yuque-doc-edit-staged, yuque-knowledge-link）
- `read_skill("yuque-doc-edit-staged")`：读取 staged skill 的 metadata
  - 包含 `initial_stage: "analysis"`
  - 包含 `stages: [analysis, execution, verification]`
  - verification stage 有 `allowed_next_stages: []`（终止阶段）
- `read_skill("yuque-knowledge-link")`：读取 no-stage skill 的 metadata
  - 无 `stages` 字段
  - 使用 skill-level `allowed_tools`
- `enable_skill("yuque-doc-edit-staged")`：启用 staged skill
  - current_stage 初始化为 "analysis"
- `PreToolUse` with analysis-stage tool：允许
- `PreToolUse` with execution-stage tool：拒绝（不在当前 stage）

**验证点**：
- ✅ Staged skills 暴露 initial_stage、stages、per-stage allowed_tools
- ✅ No-stage skills 使用 skill-level allowed_tools（fallback 行为）
- ✅ Terminal stages 有 allowed_next_stages: []
- ✅ 未授权工具（来自其他 stage）被拒绝

---

#### Scenario 02: Staged Workflow

**主题**：Stage transition governance (legal/illegal transitions, active_tools changes)

**演示内容**：
- `enable_skill("yuque-doc-edit-staged")`：启用技能，进入 analysis stage
- `PreToolUse` with `yuque_get_doc`：允许（analysis stage 工具）
- `change_stage("yuque-doc-edit-staged", "verification")`：非法转移
  - 从 analysis 只能转到 execution
  - 返回错误 "stage_transition_not_allowed"
  - audit_log 记录 "stage.transition.deny"
- `change_stage("yuque-doc-edit-staged", "execution")`：合法转移
  - 从 analysis 可以转到 execution
  - 返回成功，new_active_tools 更新
  - audit_log 记录 "stage.transition.allow"
- `PreToolUse` with `yuque_update_doc`：允许（execution stage 工具）
- `change_stage("yuque-doc-edit-staged", "verification")`：合法转移到终止阶段
- `change_stage("yuque-doc-edit-staged", "analysis")`：非法转移
  - verification 是终止阶段，allowed_next_stages: []
  - 返回错误 "stage_transition_not_allowed"

**验证点**：
- ✅ Stage transition governance 强制 allowed_next_stages
- ✅ 非法转移被拒绝，不修改状态
- ✅ 合法转移更新 current_stage 和 active_tools
- ✅ Terminal stage 阻止所有转移

---

#### Scenario 03: Lifecycle

**主题**：Terminal stages, TTL expiration, stage state persistence

**演示内容**：
- `enable_skill` with short TTL：创建短期授权
- 等待 TTL 过期
- `PreToolUse`：拒绝（grant 已过期）
- audit_log 记录 "grant.expire"
- `disable_skill`：主动禁用技能
- audit_log 记录 "skill.disable"
- Stage state persistence：验证 current_stage、stage_history、exited_stages 持久化

**验证点**：
- ✅ TTL 过期后 grant 失效
- ✅ 过期 grant 的 skill 不贡献工具到 active_tools
- ✅ disable_skill 主动撤销授权
- ✅ Stage lifecycle 字段持久化到 SQLite

---

### 这些 scenario 如何对应当前治理模型

| 治理模型概念 | Scenario 01 | Scenario 02 | Scenario 03 |
|------------|------------|------------|------------|
| Skill discovery | ✅ list_skills, read_skill | - | - |
| Staged vs no-stage | ✅ 对比两种 skill | - | - |
| initial_stage | ✅ enable 时初始化 | ✅ 进入 analysis | - |
| allowed_next_stages | ✅ 读取 metadata | ✅ 强制检查 | - |
| Terminal stage | ✅ verification 有 [] | ✅ 阻止转移 | ✅ 持久化 |
| Stage transition | - | ✅ 合法/非法转移 | - |
| active_tools 计算 | ✅ 按 stage 过滤 | ✅ 转移后更新 | - |
| Grant 创建 | ✅ enable_skill | - | ✅ 短 TTL |
| Grant 过期 | - | - | ✅ TTL 过期 |
| Grant 撤销 | - | - | ✅ disable_skill |
| PreToolUse 检查 | ✅ allow/deny | ✅ stage 工具检查 | ✅ 过期后拒绝 |
| Audit events | ✅ 基础事件 | ✅ stage.transition.* | ✅ grant.expire |

---

### 哪些概念在 demo 中最容易被观察到

**最直观的概念**（通过 demo 输出直接可见）：
1. **active_tools 变化**：enable_skill 和 change_stage 返回 new_active_tools
2. **Stage transition 拒绝**：change_stage 返回错误信息和 error_bucket
3. **PreToolUse deny**：返回 permissionDecisionReason 和 additionalContext
4. **Audit events**：events.jsonl 和 audit_summary.md 展示完整事件链

**需要查看数据库的概念**：
1. **current_stage 持久化**：查询 sessions 表的 state_json
2. **stage_history**：查询 LoadedSkillInfo.stage_history
3. **Grant 过期**：查询 grants 表的 expires_at 和 status

**需要理解代码的概念**：
1. **RuntimeContext 构建**：代码层面的派生逻辑
2. **allowed_tools vs active_tools**：声明式 vs 运行时的区别
3. **blocked_tools 过滤**：在 build_runtime_context 中的过滤逻辑

---

## 11. 最终总结

### 11.1 当前能力治理模型的核心闭环

Stagewise-Tool-Gate 实现了一个 **Skill → Stage → Grant → RuntimeContext → active_tools → PreToolUse** 的完整闭环：

1. **Skill 定义能力边界**：通过 SKILL.md 声明 allowed_tools 或 stages
2. **Stage 控制渐进演进**：通过 allowed_next_stages 强制状态机转移
3. **Grant 记录授权凭证**：通过 enable_skill 创建，带 TTL 和 scope
4. **RuntimeContext 派生运行时视图**：每回合从 SessionState 计算 active_tools
5. **active_tools 是准入白名单**：META_TOOLS ∪ stage_tools − blocked_tools
6. **PreToolUse 执行准入检查**：tool_name in active_tools? allow : deny

**关键设计决策**：
- **声明式 vs 运行时分离**：allowed_tools 是声明，active_tools 是派生
- **持久化 vs 派生分离**：SessionState 持久化，RuntimeContext 每回合重建
- **Stage-first governance**：staged skill 的工具完全由 current_stage 决定
- **安全降级**：metadata 缺失、grant 过期、stage 不匹配 → 贡献 0 工具

---

### 11.2 allowed_tools / active_tools / RuntimeContext 的关系

**三者定位**：
- **allowed_tools**：声明式工具列表，定义在 SKILL.md 中（skill-level 或 stage-level）
- **active_tools**：运行时工具集合，由 RuntimeContext 计算，是 PreToolUse 的准入白名单
- **RuntimeContext**：每回合派生的只读快照，包含 active_tools、enabled_skills、metadata、policy

**数据流**：
```
SKILL.md (allowed_tools)
    ↓ 解析
SkillMetadata (allowed_tools / stages)
    ↓ 缓存
SkillIndexer
    ↓ 读取
build_runtime_context(state, metadata, blocked_tools)
    ↓ 计算
    for each enabled skill with valid grant:
        tools += get_stage_tools(meta, current_stage)
    tools -= blocked_tools
    ↓ 输出
RuntimeContext.active_tools
    ↓ 检查
PreToolUse: tool_name in active_tools?
```

**关键公式**：
```
active_tools = META_TOOLS ∪ (⋃ enabled_skills 的 stage_tools) − blocked_tools

stage_tools = get_stage_tools(meta, current_stage)
    - Staged skill: stage.allowed_tools
    - No-stage skill: skill.allowed_tools
```

---

### 11.3 当前 demo 如何证明这个模型可运行

**simulator-demo 提供完整证明**：

1. **子进程隔离证明协议正确性**：
   - Hook 子进程（tg-hook）和 MCP 子进程（tg-mcp）独立运行
   - 通过 stdin/stdout JSON 通信
   - 通过 SQLite 共享状态
   - 证明模型可以在真实的进程边界下工作

2. **三个 scenario 覆盖核心路径**：
   - Scenario 01：Skill discovery + Stage-first metadata + PreToolUse 拒绝
   - Scenario 02：Stage transition governance + allowed_next_stages + Terminal stage
   - Scenario 03：Grant lifecycle + TTL expiration + disable_skill

3. **完整审计链证明可观测性**：
   - audit_log 表记录所有治理决策事件
   - events.jsonl 记录完整事件流水
   - audit_summary.md 生成人类可读的审计报告
   - metrics.json 提供量化指标

4. **验证脚本证明正确性**：
   - `verify_stage_first.py` 验证 Stage-first governance 行为
   - 检查 initial_stage、allowed_next_stages、terminal stage
   - 检查 audit events 完整性

**可运行性证明**：
- ✅ 真实子进程边界（不是 mock）
- ✅ 真实 SQLite 持久化（不是内存）
- ✅ 真实协议通信（stdin/stdout JSON）
- ✅ 完整事件覆盖（discovery → enable → transition → expire → disable）
- ✅ 自动化验证（verify_stage_first.py）

---

## 附录：当前模型不包含的概念

以下概念在当前代码中**不存在**或**已废弃**，本文档不作为核心概念介绍：

1. **whitelist**：当前代码没有名为 "whitelist" 的变量、字段、函数或错误类型。active_tools 是准入白名单的实现，但不使用 "whitelist" 命名。

2. **旧的 allowed_tools 持久化**：active_tools 和 skills_metadata 已标记为派生字段，不再持久化到 SQLite。

3. **旧的 ToolRewriter.recompute_active_tools(state)**：已标记为 DEPRECATED，新代码使用 `compute_active_tools(RuntimeContext)`。

4. **专门的 "tool_blocked" 错误类型**：被 blocked 的工具归类为 "tool_not_available"，没有专门的错误类型。

5. **Legacy examples 的治理模式**：01-03 样例不演示 Stage-first governance，已标记为 DEPRECATED。

---

**文档结束**

