## Why

当前代码已经实现了 Stage 的基础运行时能力（`StageDefinition`、`current_stage`、`allowed_tools`、`change_stage`），但缺少正式的 metadata 规范和 authoring 标准。这导致 Skill 容易被误解为"工具分组"而非"业务流程 SOP"。本 change 正式定义 Stage workflow 的 metadata schema 和 Skill Stage 拆分标准，为后续运行时状态机治理（initial_stage 自动进入、allowed_next_stages 校验）奠定基础。

## What Changes

- **规范 Stage workflow metadata**：
  - 定义 `initial_stage` 字段（可选，指定 enable_skill 后进入的初始 stage）
  - 定义 `allowed_next_stages` 字段（每个 stage 声明允许跳转的后续 stage 列表）
  - 明确 terminal stage 表达方式：`allowed_next_stages: []` 表示该 stage 为终止状态，后续 runtime change 中应被解释为不允许继续跳转（本 change 只定义 metadata 语义，不实现运行时校验）
  - 明确 stage-level `allowed_tools` 作为工具治理边界

- **新增 Skill Stage authoring 标准文档**：
  - 路径：`docs/skill_stage_authoring.md`
  - 内容：何时拆 Skill、何时拆 Stage、何时保留简单 skill.allowed_tools、initial_stage 选择、allowed_next_stages 设计、terminal stage 表达、反例（按工具机械拆分）

- **规范 `read_skill` / `SkillContent` 返回 stage workflow 信息**：
  - `SkillContent` 应暴露 `initial_stage`、各 stage 的 `allowed_next_stages`
  - 为 Claude 提供完整的 stage workflow 上下文

- **明确旧 examples 后续处理方向**：
  - 旧 examples（`01-knowledge-link`、`02-doc-edit-staged`、`03-lifecycle-and-risk`）后续标记为 deprecated
  - Stage-first 验收对象为 `examples/simulator-demo`

- **为后续 runtime change 定义清晰边界**：
  - 本 change 只做 metadata / authoring 规范
  - 运行时状态机（enable_skill 自动进入 initial_stage、change_stage 校验 allowed_next_stages、记录 exited_stages / stage_history / stage_entered_at）留给后续 change

## Capabilities

### New Capabilities
- `stage-workflow-metadata`: Stage workflow metadata schema（`initial_stage`、`allowed_next_stages`、terminal stage 表达）
- `skill-stage-authoring-standard`: Skill Stage 拆分和设计标准文档（`docs/skill_stage_authoring.md`）

### Modified Capabilities
- `skill-content-schema`: `SkillContent` 返回值增加 stage workflow 信息（`initial_stage`、各 stage 的 `allowed_next_stages`）

## Impact

**受影响的代码模块**：
- `src/tool_governance/models/skill.py`：`SkillMetadata` 增加 `initial_stage` 字段；`StageDefinition` 增加 `allowed_next_stages` 字段
- `src/tool_governance/core/skill_indexer.py`：`read_skill` 返回的 `SkillContent` 包含完整 stage workflow 信息
- `docs/skill_stage_authoring.md`（新增）：Skill Stage authoring 标准

**不受影响**：
- 运行时状态机逻辑（`enable_skill`、`change_stage`、`RuntimeContext`）
- Hook handlers（`hook_handler.py`）
- MCP Server（`mcp_server.py`）
- 旧 examples（保持现状，后续单独标记 deprecated）

**架构决策记录**：
- 保留 `enable_skill` 语义：启用一项 SOP / 业务能力流程，而非简单的工具分组
- 无 stages Skill 是合法的持续支持格式：没有 stages 的 Skill 仍然是完全合法的格式，适用于简单、低风险、无需阶段拆分的 Skill，继续使用 `skill.allowed_tools` 作为工具治理边界。这不是"旧格式即将废弃"，而是针对不同复杂度 Skill 的两种并行支持路径
- 支持 `initial_stage`：可选 metadata 字段，如果存在则 enable_skill 后进入该 stage（运行时实现留给后续 change）
- 支持 `allowed_next_stages`：每个 stage 声明允许跳转的后续 stage，运行时强校验留给后续 change
- `allowed_next_stages: []` 的 metadata 语义：表示该 stage 为 terminal stage（终止状态），后续 runtime change 中应被解释为不允许继续跳转。本 change 只定义 metadata 语义，不实现运行时校验
- 后续运行时状态字段命名：使用 `exited_stages` 或 `exited_stage_ids`（曾经离开的 stage），而非 `completed_stages`（避免业务意义上的"完成确认"混淆）
- 无 stages 的 Skill 调用 `change_stage`：后续运行时应返回 deny / no-op，`error_bucket = skill_has_no_stages`
- examples 处理：旧 examples 不做迁移，后续标记 deprecated；Stage-first 验收对象为 `examples/simulator-demo`
