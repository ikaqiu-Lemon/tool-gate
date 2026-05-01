# 样例 01 关联报告写回任务总结

## 任务目标

将样例 01 生成的 RAG 笔记关联分析报告中的相关文档区块写回到 `rag-overview-v2` 文档。

## 已完成的工作

### 1. 分析了源材料
- 读取了 `/home/zh/tool-gate/examples/01-knowledge-link/rag_notes_linkage_report.md`
- 理解了报告中建议的关联关系和需要补充的内容

### 2. 理解了目标文档结构
- 当前 `rag-overview-v2` 文档版本: 4
- 当前内容: 简单的三段式描述
- 最后更新: 2026-04-10T09:00:00+08:00

### 3. 准备了更新内容
根据关联报告的建议，准备了以下增强内容：

#### a) 扩展三阶段说明
- 召回阶段: 向量检索 + BM25 混合方法，链接到实践文档
- Rerank 阶段: cross-encoder 精排，说明成本权衡
- 生成阶段: system 角色注入方法

#### b) 添加相关文档链接区块
- 实现细节: 链接到"向量召回与 rerank 实践"
- 质量保障: 链接到"RAG 评测 Playbook"

#### c) 添加"如何评测"章节
- 召回阶段评测方法
- 端到端评测方法
- 链接到详细的评测 Playbook

#### d) 添加"待补充内容"提示
- 生成阶段详细实践
- 端到端性能优化
- 失败案例与调试方法

### 4. 探索了 Tool Governance 工作流
- 发现并理解了 `yuque-doc-edit` 技能的两阶段工作流
- 理解了 `require_reason` 策略要求
- 理解了 analysis → execution 的阶段切换机制

### 5. 创建了执行资产
- `proposed_update_for_rag-overview-v2.md`: 详细的更新建议文档
- `execute_writeback.sh`: 可执行的写回脚本

## 遇到的技术问题

### 问题: Agent 环境中的会话管理问题

在 agent 子进程环境中，tool-governance 的会话管理存在以下问题：

1. **Grant 不持久化**: `enable_skill` 返回成功，grant 写入数据库，但在后续调用中 `grant_status` 返回空
2. **Stage 未设置**: 数据库中 `current_stage` 字段为 null
3. **工具调用被拒**: 由于会话状态不一致，`change_stage` 和 `run_skill_action` 都报错 "Skill must be enabled first"

### 根本原因分析

通过检查数据库发现：
- 每次 `enable_skill` 调用都创建了新的 session_id (auto-2539426-*)
- Agent 环境可能没有正确传递或维护 session_id
- 导致每次工具调用都在不同的会话上下文中执行

## 推荐的执行方式

### 方式 A: 使用 Claude Code CLI (推荐)

这是 README 中推荐的方式，可以保证会话一致性：

```bash
cd /home/zh/tool-gate/examples/02-doc-edit-staged

# 设置环境变量
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

# 启动 Claude Code CLI
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

然后在 CLI 中执行以下步骤：

```
1. 用户: "帮我把样例 01 输出的相关文档区块写回 rag-overview-v2"

2. Claude 会自动执行:
   - read_skill("yuque-doc-edit") - 理解技能
   - enable_skill("yuque-doc-edit", reason="将样例01的关联分析结果写回...") - 启用技能
   - yuque_get_doc("rag-overview-v2") - 读取当前内容 (analysis 阶段)
   - change_stage("yuque-doc-edit", "execution") - 切换到执行阶段
   - yuque_update_doc("rag-overview-v2", body_markdown="...", base_version=4) - 写回更新
```

### 方式 B: 使用 tg-hook 子进程 (演示用)

如果只是想演示工作流，可以使用提供的脚本：

```bash
cd /home/zh/tool-gate/examples/02-doc-edit-staged
./execute_writeback.sh
```

注意: 这个脚本使用固定的 session_id "writeback-demo" 来确保会话一致性。

### 方式 C: 手动更新 (最简单)

直接在 Yuque 中打开 `rag-overview-v2` 文档，复制 `proposed_update_for_rag-overview-v2.md` 中的"完整的更新后文档"内容。

## 更新内容预览

### 当前内容 (版本 4)
```markdown
# RAG 总览

将 RAG 拆成召回 / rerank / 生成三段。
```

### 更新后内容
完整内容见 `proposed_update_for_rag-overview-v2.md`，主要增加了：
- 三个阶段的详细说明 (约 200 字)
- 相关文档链接区块 (2 个链接)
- 如何评测章节 (约 100 字)
- 待补充内容提示 (3 项)

总字数: 从约 30 字扩展到约 500 字

## 审计追踪

如果使用方式 A 或 B 执行，可以通过以下 SQL 查看完整的审计日志：

```bash
sqlite3 $GOVERNANCE_DATA_DIR/governance.db "
SELECT 
  datetime(created_at) as time,
  event,
  subject,
  json_extract(meta, '$.decision') as decision,
  json_extract(meta, '$.stage') as stage,
  json_extract(meta, '$.reason') as reason
FROM audit_log 
WHERE session_id = 'writeback-demo' 
ORDER BY created_at;
"
```

预期会看到：
1. `skill.enable` - granted (带 reason)
2. `tool.call` - yuque_get_doc (analysis 阶段)
3. `stage.change` - analysis → execution
4. `tool.call` - yuque_update_doc (execution 阶段)

## 相关文件

- `/home/zh/tool-gate/examples/01-knowledge-link/rag_notes_linkage_report.md` - 源关联报告
- `/home/zh/tool-gate/examples/02-doc-edit-staged/proposed_update_for_rag-overview-v2.md` - 详细更新建议
- `/home/zh/tool-gate/examples/02-doc-edit-staged/execute_writeback.sh` - 执行脚本
- `/home/zh/tool-gate/examples/02-doc-edit-staged/README.md` - 样例说明文档

## 下一步行动

选择以下任一方式完成写回：

1. **推荐**: 使用 Claude Code CLI 进行交互式写回 (方式 A)
2. **演示**: 运行 `./execute_writeback.sh` 脚本 (方式 B)
3. **简单**: 手动复制粘贴内容到 Yuque (方式 C)

执行后验证：
- 检查 `rag-overview-v2` 文档版本是否更新到 5
- 确认新增的章节和链接是否正确显示
- 查看审计日志确认操作记录完整
