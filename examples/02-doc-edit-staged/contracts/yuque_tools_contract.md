# 02-doc-edit-staged · Yuque 工具契约

契约条目面向 `yuque-doc-edit` 技能的两阶段需要:analysis 阶段只读,execution 阶段写回。

---

## yuque_get_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque`(`mock_yuque_stdio.py`) |
| 角色 | 主业务工具 |
| 输入字段 | `doc_id: str` |
| 返回字段 | `id, title, body_markdown, updated_at, version` |
| 本样例作用 | analysis 阶段拉最新正文;execution 阶段在写入前再拉一遍用于版本对齐 |
| Schema | [`yuque_get_doc.schema.json`](../schemas/yuque_get_doc.schema.json) |

**示例返回**:

```json
{
  "id": "rag-overview-v2",
  "title": "RAG 检索增强 · 总览 v2",
  "body_markdown": "# RAG 总览\n\n...\n",
  "updated_at": "2026-04-10T09:00:00+08:00",
  "version": 4
}
```

---

## yuque_list_docs

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具(analysis 阶段可选使用) |
| 输入字段 | `repo_id: str` |
| 返回字段 | `docs: List[{id, title, slug, updated_at}]` |
| 本样例作用 | 若 Alice 没有预先给 `doc_id`,模型可先 list 再挑选 |
| Schema | [`yuque_list_docs.schema.json`](../schemas/yuque_list_docs.schema.json) |

**示例返回**:

```json
{
  "docs": [
    {"id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2", "slug": "rag-overview-v2", "updated_at": "2026-04-10T09:00:00+08:00"}
  ]
}
```

---

## yuque_update_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具(**仅 execution 阶段可用**) |
| 输入字段 | `doc_id: str, body_markdown: str, base_version: int` |
| 返回字段 | `ok: bool, version: int` |
| 本样例作用 | 把"相关文档"区块追加写回;`base_version` 用于演示并发版本校验,mock 总是接受传入版本 |
| Schema | [`yuque_update_doc.schema.json`](../schemas/yuque_update_doc.schema.json) |

**示例返回**:

```json
{"ok": true, "version": 5}
```
