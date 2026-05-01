#!/bin/bash
# Script to write back the linkage report content to rag-overview-v2
# This demonstrates the proper two-stage workflow for the yuque-doc-edit skill

set -e

cd "$(dirname "$0")"

# Set up environment variables
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

echo "=== Stage 1: Enable skill with reason ==="
echo '{"event":"ToolCall","session_id":"writeback-demo","tool_name":"enable_skill","tool_input":{"skill_id":"yuque-doc-edit","reason":"将样例01的关联分析结果写回 rag-overview-v2 文档","scope":"session","ttl":3600}}' | tg-hook

echo ""
echo "=== Stage 2: Read current document (analysis stage) ==="
echo '{"event":"PreToolUse","session_id":"writeback-demo","tool_name":"yuque_get_doc","tool_input":{"doc_id":"rag-overview-v2"}}' | tg-hook

echo ""
echo "=== Stage 3: Change to execution stage ==="
echo '{"event":"ToolCall","session_id":"writeback-demo","tool_name":"change_stage","tool_input":{"skill_id":"yuque-doc-edit","stage_id":"execution"}}' | tg-hook

echo ""
echo "=== Stage 4: Write back updated content ==="
# The updated content with cross-references and related documents
UPDATED_CONTENT='# RAG 总览

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
3. **失败案例与调试** - 召回失败、rerank 失败、生成失败的诊断方法'

echo '{"event":"PreToolUse","session_id":"writeback-demo","tool_name":"yuque_update_doc","tool_input":{"doc_id":"rag-overview-v2","body_markdown":"'"$(echo "$UPDATED_CONTENT" | jq -Rs .)"'","base_version":4}}' | tg-hook

echo ""
echo "=== Done ==="
echo "Check the audit log:"
echo "sqlite3 $GOVERNANCE_DATA_DIR/governance.db 'SELECT * FROM audit_log WHERE session_id=\"writeback-demo\" ORDER BY created_at;'"
