# Phase 4 §4.7 micro-benchmark results

Iterations per path: 200

| Path                         |    n |   median | p95 (ms) | max (ms) |
|------------------------------|-----:|---------:|---------:|---------:|
| SessionStart hook            |  200 |      0.451 |      0.646 |      4.443 |
| UserPromptSubmit hook        |  200 |      0.714 |      0.821 |      3.596 |
| PreToolUse hook              |  200 |      0.238 |      0.424 |      3.323 |
| PostToolUse hook             |  200 |      0.372 |      0.626 |      4.769 |
| MCP list_skills              |  200 |      0.566 |      0.629 |    227.616 |
| MCP read_skill               |  200 |      0.416 |      0.473 |      4.156 |

## Skill-index cache

- hits: 199
- misses: 1
- hit_rate: 99.50%

## Targets vs measured
- hooks p95 < 50 ms: OK
- MCP p95 < 100 ms: OK
- cache hit rate > 95 %: OK
