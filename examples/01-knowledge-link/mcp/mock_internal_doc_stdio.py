"""mock_internal_doc_stdio — confounder MCP for example 01 (knowledge-link).

**混杂变量工具**。仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。
此 MCP server **不代表**本项目支持内部 wiki 搜索业务,也不是任何主业务能力。

在样例 01 中,search_doc 与 rag_paper_search 并列作为两个"另一种搜索源"同时注册,
目的是让 tool-gate 在多类搜索源同时存在时仍然只放行 SOP 声明的 yuque_search。
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
from mcp.server.fastmcp import FastMCP

_HERE = pathlib.Path(__file__).resolve().parent
_SCHEMAS = _HERE.parent / "schemas"

mcp = FastMCP("mock_internal_doc")


_SAMPLE = {
    "hits": [
        {"path": "wiki/eng/rag-note", "title": "(演示) 内部 wiki RAG 笔记", "snippet": "mock result"},
    ]
}


def _self_check() -> None:
    schema = json.load(open(_SCHEMAS / "search_doc.schema.json"))["properties"]["output"]
    try:
        jsonschema.validate(_SAMPLE, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_internal_doc] sample violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_self_check()


@mcp.tool()
async def search_doc(keyword: str, space: str) -> dict:
    """Confounder internal-wiki search tool. Returns a stable mock hit."""
    return _SAMPLE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
