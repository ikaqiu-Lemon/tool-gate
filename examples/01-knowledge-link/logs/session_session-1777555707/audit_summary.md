# Agent Run Audit Summary

## 1. 基础信息
- **Session ID**: session-1777555707
- **开始时间**: 2026-04-30T13:28:27.666470+00:00
- **结束时间**: 2026-04-30T13:28:32.198153+00:00
- **总耗时**: 4.53 秒
- **工作目录**: /home/zh/tool-gate/examples/01-knowledge-link

## 2. 用户请求
```
帮我把最近的 RAG 笔记做一下关联,顺便查下最新 RAG 论文
```

## 3. Skill 暴露与读取

| 阶段 | 数量 |
|------|------|
| shown (list_skills) | 1 |
| read (read_skill) | 1 |
| enabled (enable_skill) | 1 |

## 4. 工具调用统计

| 指标 | 数值 |
|------|------|
| 总调用数 | 5 |
| 成功 | 4 |
| 被拒绝 | 1 |
| 工具不可用 | 1 |

## 5. 工具调用明细

| # | 时间 | 工具 | 决策 | Error Bucket | 说明 |
|---|------|------|------|--------------|------|
| 1 | 13:28:30 | yuque_search | allow | None | ✅ 在白名单内 |
| 2 | 13:28:30 | yuque_get_doc | allow | None | ✅ 在白名单内 |
| 3 | 13:28:30 | yuque_get_doc | allow | None | ✅ 在白名单内 |
| 4 | 13:28:30 | yuque_get_doc | allow | None | ✅ 在白名单内 |
| 5 | 13:28:31 | rag_paper_search | deny | tool_not_available | ❌ Tool 'mcp__mock-web-search__ra |


## 6. 治理效果

- ✅ Skill 治理链路生效
- ✅ 成功拦截白名单外工具调用
- ✅ 无误调用或授权异常

## 7. 任务完成情况

**任务目标**: 关联 RAG 笔记 + 搜索最新 RAG 论文

**完成情况**:
- ✅ 成功关联 RAG 笔记（通过 yuque-knowledge-link skill）
- ❌ 无法搜索最新论文（rag_paper_search 工具被拒绝）

**原因分析**:
- `rag_paper_search` 工具不在 yuque-knowledge-link skill 的白名单中
- 需要单独的 web-search skill 来支持在线搜索功能

**建议**:
- 创建独立的 web-search skill，包含 rag_paper_search 工具
- 或将 rag_paper_search 添加到 yuque-knowledge-link 的 allowed_tools 中
