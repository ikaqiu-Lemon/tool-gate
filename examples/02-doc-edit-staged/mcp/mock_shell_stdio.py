"""mock_shell_stdio — 混杂变量工具(confounder)for example 02 (doc-edit-staged).

**混杂变量工具**。此 MCP server 仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。
它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。

在样例 02 中,run_command 被列入 config/demo_policy.yaml 的全局 blocked_tools;
PreToolUse 会在任何情况下 deny,因此此 handler 的返回值实际上永远不会传给模型。
这里保留硬编码样本 + schema 自检,只是为了:
1. 让 list_tools 目录里真的出现 run_command,使"Alice 误调 shell"的混杂情形能发生
2. 让 Phase B 的 jsonschema 自检对每个注册工具都有对应校验,不留漏网
"""

from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
from mcp.server.fastmcp import FastMCP

_HERE = pathlib.Path(__file__).resolve().parent
_SCHEMAS = _HERE.parent / "schemas"

mcp = FastMCP("mock_shell")


_SAMPLE = {
    "stdout": "(mock) Filesystem  Size  Used  Avail\n/dev/sda1   50G   32G   18G\n",
    "stderr": "",
    "exit_code": 0,
}


def _self_check() -> None:
    schema = json.load(open(_SCHEMAS / "run_command.schema.json"))["properties"]["output"]
    try:
        jsonschema.validate(_SAMPLE, schema)
    except jsonschema.ValidationError as e:
        print(f"[mock_shell] sample violates output schema: {e.message}", file=sys.stderr)
        sys.exit(1)


_self_check()


@mcp.tool()
async def run_command(cmd: str, cwd: str | None = None) -> dict:
    """Confounder shell-exec tool. Always returns a fixed mock stdout. **No actual shell
    execution happens** — this handler returns hardcoded text regardless of `cmd`.
    In demo context, PreToolUse denies before this runs anyway (blocked_tools)."""
    return _SAMPLE


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
