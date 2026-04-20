"""mock_yuque_stdio — Yuque 风格 mock MCP server for example 03 (lifecycle-and-risk).

演示用 stdio MCP server,聚焦生命周期与风险升级。暴露 yuque_search / yuque_list_docs /
yuque_get_doc / yuque_update_doc / yuque_delete_doc 五个工具。

yuque_delete_doc 是**高风险工具**,在 demo_policy.yaml 的 blocked_tools 中;
任何调用都会被 tool-gate 在 PreToolUse 阶段 deny,此 handler 的返回值实际永远不会传给模型。
保留它只是为了让 list_tools 目录里真的包含这个工具,使两层防线(approval_required +
blocked_tools)都能被真实触发。
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


_SEARCH_ITEMS = {
    "items": [
        {"id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2", "snippet": "一页笔记。", "repo_id": "team-rag"},
    ]
}

_LIST_DOCS = {
    "docs": [
        {"id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2", "slug": "rag-overview-v2", "updated_at": "2026-04-10T09:00:00+08:00"},
        {"id": "old-2023",        "title": "(演示) 2023 归档",        "slug": "old-2023",        "updated_at": "2023-12-01T09:00:00+08:00"},
    ]
}

_DOC = {
    "id": "rag-overview-v2",
    "title": "RAG 检索增强 · 总览 v2",
    "body_markdown": "# RAG 总览\n\n将 RAG 拆成召回 / rerank / 生成三段。\n",
    "updated_at": "2026-04-10T09:00:00+08:00",
}

_UPDATE_RESULT = {"ok": True, "version": 6}

_DELETE_RESULT = {"ok": True, "deleted_id": "old-2023"}


def _check(tool: str, sample: dict) -> None:
    schema = json.load(open(_SCHEMAS / f"{tool}.schema.json"))["properties"]["output"]
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_yuque] sample for {tool} violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_check("yuque_search", _SEARCH_ITEMS)
_check("yuque_list_docs", _LIST_DOCS)
_check("yuque_get_doc", _DOC)
_check("yuque_update_doc", _UPDATE_RESULT)
_check("yuque_delete_doc", _DELETE_RESULT)


@mcp.tool()
async def yuque_search(query: str, type: str = "doc") -> dict:
    """Yuque-style search. Returns a fixed single-result sample."""
    return _SEARCH_ITEMS


@mcp.tool()
async def yuque_list_docs(repo_id: str) -> dict:
    """List docs including an archived entry (for bulk-delete demo)."""
    return _LIST_DOCS


@mcp.tool()
async def yuque_get_doc(doc_id: str) -> dict:
    """Fetch a doc body. Returns the RAG overview sample."""
    return _DOC


@mcp.tool()
async def yuque_update_doc(doc_id: str, body_markdown: str) -> dict:
    """Write-back. Mock accepts and bumps version to 6."""
    return _UPDATE_RESULT


@mcp.tool()
async def yuque_delete_doc(doc_id: str, confirm: bool) -> dict:
    """High-risk delete. In this example `blocked_tools` denies at PreToolUse,
    so this handler is unreachable in practice. Kept for schema coverage only."""
    return _DELETE_RESULT


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
