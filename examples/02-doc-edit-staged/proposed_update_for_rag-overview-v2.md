# 建议写回 rag-overview-v2 的内容

基于样例 01 的关联分析报告，以下是建议追加到 `rag-overview-v2` 文档的内容：

## 当前文档内容

```markdown
# RAG 总览

将 RAG 拆成召回 / rerank / 生成三段。
```

**版本**: 4  
**最后更新**: 2026-04-10T09:00:00+08:00

---

## 建议追加的内容

### 1. 扩展三阶段说明

```markdown
# RAG 总览

将 RAG 拆成召回 / rerank / 生成三段。

## 三个关键阶段

### 召回 (Retrieval)
- **方法**: 向量检索 + BM25 混合检索
- **目标**: 从大规模文档库中快速召回候选文档集
- **详细实践**: 参见 [向量召回与 rerank 实践](yuque://vector-recall-best)

### Rerank (重排序)
- **方法**: 使用 cross-encoder 在小候选集上做精排
- **目标**: 对召回的候选文档进行精确排序，提升相关性
- **成本权衡**: bi-encoder (召回阶段) vs cross-encoder (rerank阶段) 的成本曲线分析详见实践文档

### 生成 (Generation)
- **方法**: 把命中片段以 system 角色注入到 LLM prompt 中
- **目标**: 基于检索到的上下文生成准确、相关的回答
```

### 2. 添加相关文档链接区块

```markdown
## 相关文档

### 实现细节
- [向量召回与 rerank 实践](yuque://vector-recall-best) - 深入对比 bi-encoder 和 cross-encoder 的成本权衡

### 质量保障
- [RAG 评测 Playbook](yuque://rag-eval-playbook) - 离线 Recall@K + 在线 golden set 双层评测方法

## 如何评测

要验证 RAG 系统的效果，建议使用以下评测方法：

1. **召回阶段评测**: 使用 Recall@K 指标衡量召回效果
2. **端到端评测**: 使用 golden set 进行在线评测
3. **详细方法**: 参见 [RAG 评测 Playbook](yuque://rag-eval-playbook)
```

### 3. 添加知识缺口提示

```markdown
## 待补充内容

基于当前知识库分析，以下主题值得进一步补充：

1. **生成阶段的详细实践** - prompt engineering 技巧和上下文窗口管理
2. **端到端性能优化** - 三阶段的延迟分布和成本占比
3. **失败案例与调试** - 召回失败、rerank 失败、生成失败的诊断方法
```

---

## 完整的更新后文档

```markdown
# RAG 总览

将 RAG 拆成召回 / rerank / 生成三段。

## 三个关键阶段

### 召回 (Retrieval)
- **方法**: 向量检索 + BM25 混合检索
- **目标**: 从大规模文档库中快速召回候选文档集
- **详细实践**: 参见 [向量召回与 rerank 实践](yuque://vector-recall-best)

### Rerank (重排序)
- **方法**: 使用 cross-encoder 在小候选集上做精排
- **目标**: 对召回的候选文档进行精确排序，提升相关性
- **成本权衡**: bi-encoder (召回阶段) vs cross-encoder (rerank阶段) 的成本曲线分析详见实践文档

### 生成 (Generation)
- **方法**: 把命中片段以 system 角色注入到 LLM prompt 中
- **目标**: 基于检索到的上下文生成准确、相关的回答

## 相关文档

### 实现细节
- [向量召回与 rerank 实践](yuque://vector-recall-best) - 深入对比 bi-encoder 和 cross-encoder 的成本权衡

### 质量保障
- [RAG 评测 Playbook](yuque://rag-eval-playbook) - 离线 Recall@K + 在线 golden set 双层评测方法

## 如何评测

要验证 RAG 系统的效果，建议使用以下评测方法：

1. **召回阶段评测**: 使用 Recall@K 指标衡量召回效果
2. **端到端评测**: 使用 golden set 进行在线评测
3. **详细方法**: 参见 [RAG 评测 Playbook](yuque://rag-eval-playbook)

## 待补充内容

基于当前知识库分析，以下主题值得进一步补充：

1. **生成阶段的详细实践** - prompt engineering 技巧和上下文窗口管理
2. **端到端性能优化** - 三阶段的延迟分布和成本占比
3. **失败案例与调试** - 召回失败、rerank 失败、生成失败的诊断方法
```

---

## 执行说明

由于当前 agent 环境中的 governance 系统存在会话管理问题，无法直接执行写回操作。建议通过以下方式之一完成写回：

### 方式 A: 使用 Claude Code CLI (推荐)
```bash
cd /home/zh/tool-gate/examples/02-doc-edit-staged
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

然后在 Claude Code CLI 中执行：
1. `enable_skill("yuque-doc-edit", reason="将样例01的关联分析结果写回 rag-overview-v2 文档")`
2. `yuque_get_doc("rag-overview-v2")` - 在 analysis 阶段读取最新内容
3. `change_stage("yuque-doc-edit", "execution")` - 切换到 execution 阶段
4. `yuque_update_doc("rag-overview-v2", body_markdown="<上述完整内容>", base_version=4)` - 写回更新

### 方式 B: 手动更新
直接在 Yuque 中打开 `rag-overview-v2` 文档，将上述"完整的更新后文档"内容复制粘贴进去。
