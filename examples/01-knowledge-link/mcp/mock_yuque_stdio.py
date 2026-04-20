"""mock_yuque_stdio — Yuque 风格 mock MCP server for example 01 (knowledge-link).

演示用 stdio MCP server。暴露 yuque_search / yuque_list_docs / yuque_get_doc /
yuque_update_doc / yuque_list_comments 五个工具。所有返回值都是硬编码样本,
启动时用 ../schemas/*.schema.json 做 jsonschema 自检,任一样本不合规即非零退出。

本文件属于 examples/01-knowledge-link workspace。演示目的:
- yuque_search / list_docs / get_doc  : 主业务工具,服务 yuque-knowledge-link 技能
- yuque_update_doc                    : 仅作为越界 deny 路径的被拦对象(主线不命中)
- yuque_list_comments                 : refresh_skills 插曲触发后对应 yuque-comment-sync 技能
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
from mcp.server.fastmcp import FastMCP

_HERE = pathlib.Path(__file__).resolve().parent
_SCHEMAS = _HERE.parent / "schemas"

mcp = FastMCP("mock_yuque")


# --- Hardcoded samples ---------------------------------------------------

_SEARCH_ITEMS = {
    "items": [
        {"id": "rag-overview-v2",   "title": "RAG 检索增强 · 总览 v2", "snippet": "一页笔记:把 RAG 拆成召回 / rerank / 生成三段。",  "repo_id": "team-rag"},
        {"id": "vector-recall-best", "title": "向量召回与 rerank 实践", "snippet": "对比 bi-encoder 与 cross-encoder 的成本曲线。", "repo_id": "team-rag"},
        {"id": "rag-eval-playbook",  "title": "RAG 评测 Playbook",       "snippet": "离线 Recall@K、在线 golden set 的双层做法。",    "repo_id": "team-rag"},
    ]
}

_LIST_DOCS = {
    "docs": [
        {"id": "rag-overview-v2",    "title": "RAG 检索增强 · 总览 v2", "slug": "rag-overview-v2", "updated_at": "2026-04-10T09:00:00+08:00"},
        {"id": "vector-recall-best", "title": "向量召回与 rerank 实践", "slug": "vector-recall",   "updated_at": "2026-04-12T16:30:00+08:00"},
        {"id": "rag-eval-playbook",  "title": "RAG 评测 Playbook",       "slug": "rag-eval",        "updated_at": "2026-04-15T11:20:00+08:00"},
    ]
}

_DOC_BODIES = {
    "rag-overview-v2": {
        "id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2",
        "body_markdown": "# RAG 总览\n\n将 RAG 拆成召回 / rerank / 生成三段。\n\n- 召回:向量 + BM25 混合\n- rerank:cross-encoder 在小候选集上做精排\n- 生成:把命中片段以 system 角色注入\n",
        "updated_at": "2026-04-10T09:00:00+08:00",
    },
    "vector-recall-best": {
        "id": "vector-recall-best", "title": "向量召回与 rerank 实践",
        "body_markdown": "# 向量召回与 rerank\n\n实测 bi-encoder vs cross-encoder 的成本曲线。\n",
        "updated_at": "2026-04-12T16:30:00+08:00",
    },
    "rag-eval-playbook": {
        "id": "rag-eval-playbook", "title": "RAG 评测 Playbook",
        "body_markdown": "# RAG 评测\n\n离线 Recall@K + 在线 golden set 双层。\n",
        "updated_at": "2026-04-15T11:20:00+08:00",
    },
}

_UPDATE_SAMPLE = {"ok": True, "version": 4}

_COMMENTS_SAMPLE = {
    "comments": [
        {"id": "c-001", "author": "bob",   "body": "这段的召回比例 Top-K 建议写清楚", "created_at": "2026-04-18T14:02:11+08:00"},
        {"id": "c-002", "author": "carol", "body": "rerank 那段能不能补个 cost 对照", "created_at": "2026-04-18T15:47:00+08:00"},
    ]
}


# --- Self-check (runs at import) -----------------------------------------

def _load_schema(tool: str) -> dict:
    return json.load(open(_SCHEMAS / f"{tool}.schema.json"))


def _check(tool: str, sample: dict) -> None:
    schema = _load_schema(tool)["properties"]["output"]
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_yuque] sample for {tool} violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_check("yuque_search", _SEARCH_ITEMS)
_check("yuque_list_docs", _LIST_DOCS)
for _body in _DOC_BODIES.values():
    _check("yuque_get_doc", _body)
_check("yuque_update_doc", _UPDATE_SAMPLE)
_check("yuque_list_comments", _COMMENTS_SAMPLE)


# --- Tools ----------------------------------------------------------------

@mcp.tool()
async def yuque_search(query: str, type: str = "doc") -> dict:
    """Yuque-style global search. Returns hardcoded RAG candidates regardless of query."""
    return _SEARCH_ITEMS


@mcp.tool()
async def yuque_list_docs(repo_id: str) -> dict:
    """List docs inside a repo. Returns a fixed 3-doc list."""
    return _LIST_DOCS


@mcp.tool()
async def yuque_get_doc(doc_id: str) -> dict:
    """Fetch a single doc body. Falls back to rag-overview-v2 if doc_id is unknown."""
    return _DOC_BODIES.get(doc_id, _DOC_BODIES["rag-overview-v2"])


@mcp.tool()
async def yuque_update_doc(doc_id: str, body_markdown: str) -> dict:
    """Write-back endpoint. In example 01 this tool is outside the skill's allowed_tools;
    PreToolUse should deny before the request reaches this handler."""
    return _UPDATE_SAMPLE


@mcp.tool()
async def yuque_list_comments(doc_id: str) -> dict:
    """Unlocked by the refresh_skills episode. Returns two demo comments."""
    return _COMMENTS_SAMPLE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
