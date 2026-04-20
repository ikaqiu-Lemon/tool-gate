# 02-doc-edit-staged · Shell 工具契约

> ⚠️ **关于 `mock_shell_stdio.py` 的角色**
>
> 此 MCP server 是**混杂变量工具**,仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。
>
> 在本样例中,`run_command` 被列入 `config/demo_policy.yaml` 的全局 `blocked_tools`,因此无论哪个技能在任何阶段尝试调用,`PreToolUse` 都会返回 `deny reason=blocked`。该工具仅用于验证**全局红线**路径,不进入任何技能的 `allowed_tools`。

---

## run_command

| 字段 | 值 |
|---|---|
| 所在 MCP | `mock-shell`(`mock_shell_stdio.py`) |
| 角色 | **混杂变量工具**(永不放行) |
| 输入字段 | `cmd: str, cwd: str (optional)` |
| 返回字段 | `stdout: str, stderr: str, exit_code: int` |
| 本样例作用 | Alice 可能因肌肉记忆试图 `df -h` 之类;验证 `blocked_tools` 在任何上下文都能拦住 |
| Schema | [`run_command.schema.json`](../schemas/run_command.schema.json) |

**示例返回**(仅供 schema 校验;Phase B 实际上模型永远收不到该返回,因为 `PreToolUse` 会先 deny):

```json
{"stdout": "(mock) Filesystem  Size  Used  Avail\n/dev/sda1   50G   32G   18G\n", "stderr": "", "exit_code": 0}
```
