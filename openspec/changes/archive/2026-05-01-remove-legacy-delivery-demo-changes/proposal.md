## Why

当前仓库中存在两个 legacy delivery-demo changes，它们共同塑造了 `examples/` 下的 demo 路线，但现在已成为历史叠加问题：

1. **Archived change**: `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` — 最初创建了三个 demo workspaces 的基础结构
2. **Active change**: `openspec/changes/harden-demo-workspace-onboarding/` — 后续强化了 onboarding 文档与 beginner-runnability

这两个 changes 的问题：

- **Active change 仍在 `openspec list` 中出现**，干扰后续工作流，给人"demo 路线尚未完成"的错觉
- **Archived change 作为 creation milestone** 已完成历史使命，但其 artifacts 仍占据 archive 空间
- **未来任何人或模型**阅读 `openspec/changes/` 时会默认把这两个 changes 当作 demo 的 canonical source of truth，而实际上 demo 的真相源应该是当前 `examples/` 目录本身和 `openspec/specs/delivery-demo-harness/`
- **无法直接删除**：这两个 changes 的 specs delta、设计决策、契约定义等内容可能仍被当前 specs 或文档引用

本次 change 的目标不是简单删目录，而是：

1. **通过 OpenSpec 新建一个 cleanup/supersede change**，明确接管 demo 的 source of truth
2. **在删除前产出完整影响报告**：代码、文档、规格的影响面分析
3. **迁移 source-of-truth**：让主 specs 和仓库入口不再依赖这两个 legacy changes
4. **安全删除**：只有在确认影响分析完成、迁移完成后，才删除旧 change 目录
5. **验证完整性**：删除后 `openspec validate --all` 仍然通过，`openspec list` 不再出现 legacy changes

为什么必须通过 OpenSpec change 来做：

- **可追溯性**：删除决策、影响分析、迁移路径都记录在 change artifacts 中
- **可验证性**：通过 specs delta 明确表达"legacy changes 不再是 canonical guidance"
- **可回滚性**：如果删除后发现问题，可以通过 change history 快速定位和恢复
- **符合工作流**：本项目所有重要变更都通过 OpenSpec 管理，cleanup 也不例外

## What Changes

本 change 将完成以下事项（按 stage 顺序）：

### Stage A：删除影响报告
- 盘点两个 legacy changes 的完整影响面
- 分析它们对 `openspec/specs/`、`examples/`、`README/QUICKSTART`、`AGENTS.md/CLAUDE.md` 的影响
- 输出结构化报告：change 状态与关系、代码与文档改动、specs 影响、仓库入口影响、删除执行建议
- **不做任何删除或修改**

### Stage B：Spec 和 Source-of-Truth 迁移
- 更新 `openspec/specs/delivery-demo-harness/` 相关 specs
- 通过 specs delta 明确表达：
  - Legacy delivery-demo changes MUST NOT be treated as canonical implementation guidance
  - Current repo navigation MUST point to `examples/` and `openspec/specs/delivery-demo-harness/` as canonical demo path
  - Archived or superseded demo changes MAY remain as historical context only (until deletion)
- 确保当前 source of truth 不再依赖这两个 legacy changes
- **不删除旧 changes，不修改 `src/` 或 `tests/`**

### Stage C：入口文档清理
- 修改仓库入口文档：根 `README.md`、`examples/README.md`、`examples/QUICKSTART.md`
- 修改 agent guidance：`AGENTS.md`、`CLAUDE.md`（如果有相关引用）
- 删除或改写默认指向 legacy demo changes 的文案
- 如果需要保留 legacy 提示，只能标注为：
  - "historical context only"
  - "not canonical"
  - "superseded by current examples/"
- **确保未来模型默认会看 `examples/` 和 `openspec/specs/delivery-demo-harness/`，而不是旧 changes**

### Stage D：移除旧 Changes 并验证
- 删除 `openspec/changes/harden-demo-workspace-onboarding/` 目录
- 删除 `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` 目录
- 运行 `openspec validate --all` 验证 specs 完整性
- 运行 `openspec list` 确认 `harden-demo-workspace-onboarding` 不再出现
- 使用 grep/ripgrep 确认仓库中不再把这两个 change 当作默认 demo 依据
- 输出最终删除结果与验证报告

## Capabilities

### New Capabilities

无。本 change 是 cleanup/supersede 操作，不引入新能力。

### Modified Capabilities

- `delivery-demo-harness`: 追加 source-of-truth 明确化需求 —— 
  - **ADDED Requirement**: Legacy delivery-demo changes (archived `add-delivery-demo-workspaces` and active `harden-demo-workspace-onboarding`) MUST NOT be treated as canonical implementation guidance for demo workspaces
  - **ADDED Requirement**: Current repository navigation (README, QUICKSTART, agent guidance) MUST point to `examples/` directory and `openspec/specs/delivery-demo-harness/` as the canonical demo source of truth
  - **ADDED Requirement**: Archived or superseded demo changes MAY be referenced as historical context only, with explicit "not canonical" disclaimers
  - **ADDED Requirement**: Deleting legacy demo change directories SHALL NOT remove still-needed current requirements from main specs without replacement
  - **MODIFIED Requirement**: Demo workspace discovery flow SHALL start from `examples/README.md` and `examples/QUICKSTART.md`, not from OpenSpec change artifacts

## Impact

### In Scope

**OpenSpec artifacts 和文档入口**（只修改这些）：
- `openspec/changes/` 目录（删除两个 legacy changes）
- `openspec/specs/delivery-demo-harness/` 相关 specs（specs delta）
- 根 `README.md`（如有 legacy change 引用）
- `examples/README.md`（如有 legacy change 引用）
- `examples/QUICKSTART.md`（如有 legacy change 引用）
- `AGENTS.md` / `CLAUDE.md`（如有 legacy change 引用）
- `docs/dev_plan.md` Addendum（更新 change 归档记录）

**产出物**：
- Stage A 删除影响报告（结构化 markdown）
- Stage B specs delta
- Stage C 文档入口修改
- Stage D 删除验证报告

### Out of Scope

**明确不修改**（防止 scope 蔓延）：
- `src/tool_governance/**` — 不修改任何运行逻辑代码
- `tests/**` — 不修改任何测试代码
- `examples/01-knowledge-link/**` — 不修改 demo workspace 内容
- `examples/02-doc-edit-staged/**` — 不修改 demo workspace 内容
- `examples/03-lifecycle-and-risk/**` — 不修改 demo workspace 内容
- `hooks/hooks.json` — 不修改 hook 配置
- `.claude-plugin/plugin.json` — 不修改 plugin manifest
- `config/default_policy.yaml` — 不修改默认策略
- `.mcp.json` — 不修改 MCP 配置

**明确不做**：
- 不做 git history rewrite（`git reset`、`git rebase`、`git filter-branch` 等）
- 不做 destructive git operations（除非用户明确批准）
- 不修改 `examples/` 下的 demo workspace 实现（skills、mcp、schemas、contracts 等）
- 不重构 demo 运行逻辑
- 不在本轮 archive 新 change（等待用户确认）

### Success Criteria

本 change 成功的标准：

1. **删除后 `openspec list` 不再出现 `harden-demo-workspace-onboarding`**
2. **仓库默认入口不再把这两个 legacy changes 当作 demo 默认依据**
3. **Demo 相关 source of truth 已明确迁移到 `examples/` 和 `openspec/specs/delivery-demo-harness/`**
4. **`openspec validate --all` 仍然通过**
5. **全程不修改 `src/` 和 `tests/` 代码**
6. **删除影响报告完整记录了两个 legacy changes 的影响面**
7. **Specs delta 明确表达了 legacy changes 不再是 canonical guidance**

### Rollback Strategy

如果删除后发现问题：

1. **Stage A/B/C 可随时回滚**：只是文档和 specs 修改，`git revert` 即可
2. **Stage D 删除后可恢复**：
   - 从 git history 恢复被删除的目录：`git checkout <commit-before-delete> -- openspec/changes/harden-demo-workspace-onboarding/`
   - 从 git history 恢复 archived change：`git checkout <commit-before-delete> -- openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`
3. **不需要数据迁移**：无 DB schema 变更，无运行时状态变更
4. **验证失败时的处理**：
   - 如果 `openspec validate --all` 失败，说明 specs 迁移不完整，需要补充 Stage B
   - 如果仓库入口仍引用 legacy changes，说明 Stage C 不完整，需要补充清理

### Risks

| 风险 | 触发场景 | 缓解 |
|---|---|---|
| **删除后 specs 不完整** | Stage B 迁移遗漏了某些 requirements | Stage A 影响报告必须完整盘点所有 specs 影响；Stage D 验证必须运行 `openspec validate --all` |
| **仓库入口仍引用 legacy changes** | Stage C 遗漏了某些文档入口 | Stage A 影响报告必须完整盘点所有入口文档；Stage D 验证必须 grep 确认无残留引用 |
| **误删仍需要的内容** | 某些 legacy change 内容实际上仍被当前系统依赖 | Stage A 影响报告必须明确区分"历史材料"和"当前依赖"；Stage B 必须先迁移所有当前依赖 |
| **`openspec list` 仍显示 legacy change** | 删除目录后 OpenSpec 缓存未刷新 | Stage D 验证必须运行 `openspec list` 并确认输出；必要时清理 OpenSpec 缓存 |
| **未来模型仍默认看 legacy changes** | 文档清理不彻底，模型仍能找到旧引用 | Stage C 必须修改所有主要入口（README、QUICKSTART、AGENTS、CLAUDE）；Stage D 必须 grep 验证 |

### Compatibility

- **向后兼容性**：完全向后兼容。删除的是 OpenSpec change artifacts，不影响 `examples/` 下的 demo workspaces 实现
- **对 `src/` 代码的兼容性**：零侵入。本 change 不读不写任何源码路径
- **对 `examples/` 的兼容性**：零侵入。demo workspaces 的 skills、mcp、schemas、contracts、policies 全部保持不变
- **对外部读者的兼容性**：已经按 `examples/QUICKSTART.md` 跑通过的用户完全不受影响；未来新用户会看到更清晰的 source of truth 指向
