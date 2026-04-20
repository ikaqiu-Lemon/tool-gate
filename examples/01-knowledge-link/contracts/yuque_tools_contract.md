# 01-knowledge-link · Mock 工具契约

所有契约条目均对应 `./schemas/*.schema.json`。Phase B 的 mock 启动时必须对自身硬编码样本做 `jsonschema.validate`,否则拒绝启动。

---

## yuque_search

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque`(`mock_yuque_stdio.py`) |
| 角色 | 主业务工具 |
| 输入字段 | `query: str`,`type: "doc" \| "repo"` |
| 返回字段 | `items: List[{id, title, snippet, repo_id}]` |
| 本样例作用 | Phase B 的主业务搜索入口;返回 Top-N 候选文档供模型收敛范围 |
| Schema | [`yuque_search.schema.json`](../schemas/yuque_search.schema.json) |

**示例返回**:

```json
{
  "items": [
    {"id": "rag-overview-v2",        "title": "RAG 检索增强 · 总览 v2", "snippet": "一页笔记:把 RAG 拆成召回 / rerank / 生成三段。", "repo_id": "team-rag"},
    {"id": "vector-recall-best",      "title": "向量召回与 rerank 实践", "snippet": "对比 bi-encoder 与 cross-encoder 的成本曲线。",   "repo_id": "team-rag"},
    {"id": "rag-eval-playbook",       "title": "RAG 评测 Playbook",      "snippet": "离线 Recall@K、在线 golden set 的双层做法。", "repo_id": "team-rag"}
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
| 本样例作用 | 当模型需要"在指定 repo 内部缩 Top-K"时获取全量候选 |
| Schema | [`yuque_list_docs.schema.json`](../schemas/yuque_list_docs.schema.json) |

**示例返回**:

```json
{
  "docs": [
    {"id": "rag-overview-v2",   "title": "RAG 检索增强 · 总览 v2", "slug": "rag-overview-v2",  "updated_at": "2026-04-10T09:00:00+08:00"},
    {"id": "vector-recall-best", "title": "向量召回与 rerank 实践", "slug": "vector-recall",    "updated_at": "2026-04-12T16:30:00+08:00"},
    {"id": "rag-eval-playbook",  "title": "RAG 评测 Playbook",     "slug": "rag-eval",         "updated_at": "2026-04-15T11:20:00+08:00"}
  ]
}
```

---

## yuque_get_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具 |
| 输入字段 | `doc_id: str`(或 `repo_id + slug`) |
| 返回字段 | `id, title, body_markdown, updated_at` |
| 本样例作用 | 对收敛后的 Top-K 候选逐篇深读,抽主题与关系 |
| Schema | [`yuque_get_doc.schema.json`](../schemas/yuque_get_doc.schema.json) |

**示例返回**:

```json
{
  "id": "rag-overview-v2",
  "title": "RAG 检索增强 · 总览 v2",
  "body_markdown": "# RAG 总览\n\n将 RAG 拆成召回 / rerank / 生成三段。\n\n- 召回:向量 + BM25 混合...\n- rerank:cross-encoder 在小候选集上做精排...\n- 生成:把命中片段以 system 角色注入...\n",
  "updated_at": "2026-04-10T09:00:00+08:00"
}
```

---

## yuque_update_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque` |
| 角色 | 主业务工具(**本样例仅作为越界 deny 路径的被拦对象**,不在 `yuque-knowledge-link.allowed_tools` 中) |
| 输入字段 | `doc_id: str, body_markdown: str` |
| 返回字段 | `ok: bool, version: int` |
| 本样例作用 | 证明即使 Alice 诱导"顺手改标题",该工具依然被 `PreToolUse` deny |
| Schema | [`yuque_update_doc.schema.json`](../schemas/yuque_update_doc.schema.json) |

**示例返回**(Phase B 正常分支,仅供 schema 校验):

```json
{"ok": true, "version": 4}
```

---

## yuque_list_comments

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-yuque`(refresh 插曲后注册) |
| 角色 | 主业务工具(属于 `yuque-comment-sync` 技能,**本样例主线不调**) |
| 输入字段 | `doc_id: str` |
| 返回字段 | `comments: List[{id, author, body, created_at}]` |
| 本样例作用 | `refresh_skills` 插曲后成为 `list_skills` 可见的新技能的工具;用来证明动态发现能力 |
| Schema | [`yuque_list_comments.schema.json`](../schemas/yuque_list_comments.schema.json) |

**示例返回**:

```json
{
  "comments": [
    {"id": "c-001", "author": "bob",   "body": "这段的召回比例 Top-K 建议写清楚", "created_at": "2026-04-18T14:02:11+08:00"},
    {"id": "c-002", "author": "carol", "body": "rerank 那段能不能补个 cost 对照", "created_at": "2026-04-18T15:47:00+08:00"}
  ]
}
```

---

## search_web

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-web-search`(`mock_web_search_stdio.py`) |
| 角色 | **混杂变量工具** |
| 输入字段 | `query: str` |
| 返回字段 | `results: List[{url, title, snippet}]` |
| 本样例作用 | 证明即使用户提示诱导"顺便上网查下",模型被拦;**不代表本项目希望模型做 Web 搜索** |
| Schema | [`search_web.schema.json`](../schemas/search_web.schema.json) |

**示例返回**(仅供 schema 校验,Phase B 实际会在 `PreToolUse` 前被 deny,不会真正返回给模型):

```json
{
  "results": [
    {"url": "https://example.com/rag-survey-2026", "title": "(演示) RAG Survey 2026", "snippet": "mock result"}
  ]
}
```

---

## search_doc

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-internal-doc`(`mock_internal_doc_stdio.py`) |
| 角色 | **混杂变量工具** |
| 输入字段 | `keyword: str, space: str` |
| 返回字段 | `hits: List[{path, title, snippet}]` |
| 本样例作用 | 证明多类搜索源同时注册时,tool-gate 只让 SOP 声明的 `yuque_search` 通过;内部 wiki 搜索被 deny |
| Schema | [`search_doc.schema.json`](../schemas/search_doc.schema.json) |

**示例返回**:

```json
{
  "hits": [
    {"path": "wiki/eng/rag-note", "title": "(演示) 内部 wiki RAG 笔记", "snippet": "mock result"}
  ]
}
```
