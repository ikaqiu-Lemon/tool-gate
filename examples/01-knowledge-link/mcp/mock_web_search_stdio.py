"""mock_web_search_stdio — confounder MCP for example 01 (knowledge-link).

**混杂变量工具**。仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。
此 MCP server **不代表**本项目支持 Web 搜索业务,也不是任何主业务能力。

在样例 01 中,rag_paper_search 不在 yuque-knowledge-link 技能的 allowed_tools 里;
PreToolUse 会在请求抵达此 handler 之前 deny。本文件的存在只为:
1. 让 .mcp.json 能真实注册一个"另一种搜索源",制造混杂
2. 让 list_tools 目录里真的出现 rag_paper_search,模型才有可能被诱导调用
3. 工具名 rag_paper_search 不会与 Claude Code 内置 WebSearch 冲突
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
from mcp.server.fastmcp import FastMCP

_HERE = pathlib.Path(__file__).resolve().parent
_SCHEMAS = _HERE.parent / "schemas"

mcp = FastMCP("mock_web_search")


_SAMPLE = {
    "papers": [
        {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "authors": ["Patrick Lewis", "Ethan Perez"],
            "year": 2020,
            "abstract": "Large pre-trained language models have been shown to store factual knowledge...",
            "url": "https://arxiv.org/abs/2005.11401"
        }
    ]
}


def _self_check() -> None:
    schema = json.load(open(_SCHEMAS / "rag_paper_search.schema.json"))["properties"]["output"]
    try:
        jsonschema.validate(_SAMPLE, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_web_search] sample violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_self_check()


@mcp.tool()
async def rag_paper_search(query: str) -> dict:
    """Confounder RAG paper search tool. Returns a stable mock result for any query.

    This tool is intentionally NOT in yuque-knowledge-link's allowed_tools,
    so it will be denied by PreToolUse. It does not conflict with Claude Code's
    built-in WebSearch tool."""
    return _SAMPLE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
