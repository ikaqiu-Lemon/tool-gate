# 03-lifecycle-and-risk · Yuque 工具契约

本样例聚焦生命周期与风险升级,因此 mock MCP 仅 `mock-yuque` 一个;无混杂变量 MCP。`yuque_delete_doc` 被 `blocked_tools` 兜底拦截。

---

## yuque_search

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具 |
| 输入字段 | `query: str, type: "doc" \| "repo"` |
| 返回字段 | `items: List[{id, title, snippet, repo_id}]` |
| 本样例作用 | TTL 过期前后各调一次,验证 `UserPromptSubmit` 重算后该工具在 `active_tools` 的出入 |
| Schema | [`yuque_search.schema.json`](../schemas/yuque_search.schema.json) |

**示例返回**:

```json
{
  "items": [
    {"id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2", "snippet": "...", "repo_id": "team-rag"}
  ]
}
```

---

## yuque_list_docs

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具 |
| 输入字段 | `repo_id: str` |
| 返回字段 | `docs: List[{id, title, slug, updated_at}]` |
| 本样例作用 | `yuque-bulk-delete` 的列举阶段可用;但本样例主线止于 approval deny |
| Schema | [`yuque_list_docs.schema.json`](../schemas/yuque_list_docs.schema.json) |

**示例返回**:

```json
{"docs": [{"id": "old-2023", "title": "(演示) 2023 归档", "slug": "old-2023", "updated_at": "2023-12-01T09:00:00+08:00"}]}
```

---

## yuque_get_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具 |
| 输入字段 | `doc_id: str` |
| 返回字段 | `id, title, body_markdown, updated_at` |
| 本样例作用 | 主线不调用;保留以覆盖复刻的 `yuque-knowledge-link` / `yuque-doc-edit` 阶段工具集 |
| Schema | [`yuque_get_doc.schema.json`](../schemas/yuque_get_doc.schema.json) |

**示例返回**:

```json
{"id": "rag-overview-v2", "title": "RAG 总览", "body_markdown": "...", "updated_at": "2026-04-10T09:00:00+08:00"}
```

---

## yuque_update_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具 |
| 输入字段 | `doc_id: str, body_markdown: str` |
| 返回字段 | `ok: bool, version: int` |
| 本样例作用 | 主线仅出现于 `disable_skill` 之前的 active_tools 快照;disable 后即失效 |
| Schema | [`yuque_update_doc.schema.json`](../schemas/yuque_update_doc.schema.json) |

**示例返回**:

```json
{"ok": true, "version": 6}
```

---

## yuque_delete_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | **高风险工具**,被 `blocked_tools` 全局拦截 |
| 输入字段 | `doc_id: str, confirm: bool` |
| 返回字段 | `ok: bool, deleted_id: str` |
| 本样例作用 | 证明"两层防线":即便跳过 approval 让 grant 存在,`yuque_delete_doc` 仍在 `blocked_tools` 中;`PreToolUse` 以 `reason=blocked` 兜底 deny |
| Schema | [`yuque_delete_doc.schema.json`](../schemas/yuque_delete_doc.schema.json) |

**示例返回**(仅供 schema 校验,Phase B 中模型永远收不到此返回):

```json
{"ok": true, "deleted_id": "old-2023"}
```
