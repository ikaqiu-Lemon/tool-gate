"""mock_yuque_stdio — Yuque 风格 mock MCP server for example 02 (doc-edit-staged).

演示用 stdio MCP server,面向**写回场景**。暴露 yuque_get_doc / yuque_list_docs /
yuque_update_doc 三个工具。所有返回值都是硬编码样本,启动时用 ../schemas/*.schema.json
做 jsonschema 自检。

本文件服务 yuque-doc-edit 技能:
- analysis 阶段:yuque_get_doc / yuque_list_docs
- execution 阶段:yuque_get_doc / yuque_update_doc(base_version 用于并发版本演示)
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


_DOC = {
    "id": "rag-overview-v2",
    "title": "RAG 检索增强 · 总览 v2",
    "body_markdown": "# RAG 总览\n\n将 RAG 拆成召回 / rerank / 生成三段。\n",
    "updated_at": "2026-04-10T09:00:00+08:00",
    "version": 4,
}

_LIST_DOCS = {
    "docs": [
        {"id": "rag-overview-v2", "title": "RAG 检索增强 · 总览 v2", "slug": "rag-overview-v2", "updated_at": "2026-04-10T09:00:00+08:00"},
    ]
}

_UPDATE_RESULT = {"ok": True, "version": 5}


def _check(tool: str, sample: dict) -> None:
    schema = json.load(open(_SCHEMAS / f"{tool}.schema.json"))["properties"]["output"]
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_yuque] sample for {tool} violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_check("yuque_get_doc", _DOC)
_check("yuque_list_docs", _LIST_DOCS)
_check("yuque_update_doc", _UPDATE_RESULT)


@mcp.tool()
async def yuque_get_doc(doc_id: str) -> dict:
    """Pull latest doc body. Returns a fixed sample including version for conflict demo."""
    return _DOC


@mcp.tool()
async def yuque_list_docs(repo_id: str) -> dict:
    """List docs of a repo. Returns a single-entry list for the demo doc."""
    return _LIST_DOCS


@mcp.tool()
async def yuque_update_doc(doc_id: str, body_markdown: str, base_version: int | None = None) -> dict:
    """Execution-stage write-back. Mock always accepts and bumps version to 5."""
    return _UPDATE_RESULT


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
