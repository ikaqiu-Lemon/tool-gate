"""Phase 4 §4.7 — local micro-benchmarks for governance hot paths.

Runs a representative workload against an in-memory GovernanceRuntime and
reports median / p95 latencies for each hook plus the governance MCP
tools, alongside the skill-index cache hit rate.

The numbers are not load-test grade — they exist to verify the targets
named in ``openspec/changes/build-tool-governance-plugin/tasks.md``
§4.7:

- PreToolUse / PostToolUse / UserPromptSubmit latency < 50 ms
- MCP tool response < 100 ms
- Skill-index cache hit rate > 95 %

Re-run locally with::

    python scripts/bench_phase4.py

Pipe the output into ``docs/perf_results.md`` to refresh the stored
results.
"""

from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from pathlib import Path

from tool_governance import hook_handler, mcp_server
from tool_governance.bootstrap import create_governance_runtime


ITERATIONS = 200


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    k = max(0, min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1)))))
    return ordered[k]


def _time_ms(fn, *args, **kwargs) -> float:
    start = time.perf_counter()
    fn(*args, **kwargs)
    return (time.perf_counter() - start) * 1000


def _time_async_ms(coro_fn, *args, **kwargs) -> float:
    start = time.perf_counter()
    asyncio.run(coro_fn(*args, **kwargs))
    return (time.perf_counter() - start) * 1000


def _summarise(label: str, samples: list[float]) -> dict[str, float]:
    return {
        "label": label,
        "median_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 95),
        "max_ms": max(samples),
        "n": len(samples),
    }


def _format_row(row: dict[str, float]) -> str:
    return (
        f"| {row['label']:<28} | {row['n']:>4} | "
        f"{row['median_ms']:>10.3f} | {row['p95_ms']:>10.3f} | {row['max_ms']:>10.3f} |"
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skills_dir = repo_root / "tests" / "fixtures" / "skills"

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        config_dir = repo_root / "config"
        rt = create_governance_runtime(data_dir, skills_dir, config_dir)
        hook_handler._runtime = rt  # reuse the pre-built runtime
        mcp_server._runtime = rt

        session_id = "bench-session"
        session_event = {"event": "SessionStart", "session_id": session_id}
        ups_event = {"event": "UserPromptSubmit", "session_id": session_id}
        pre_event = {
            "event": "PreToolUse",
            "session_id": session_id,
            "tool_name": "mock_read",
        }
        post_event = {
            "event": "PostToolUse",
            "session_id": session_id,
            "tool_name": "mock_read",
        }

        hook_handler.handle_session_start(session_event)
        asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

        session_lat = [_time_ms(hook_handler.handle_session_start, session_event) for _ in range(ITERATIONS)]
        ups_lat = [_time_ms(hook_handler.handle_user_prompt_submit, ups_event) for _ in range(ITERATIONS)]
        pre_lat = [_time_ms(hook_handler.handle_pre_tool_use, pre_event) for _ in range(ITERATIONS)]
        post_lat = [_time_ms(hook_handler.handle_post_tool_use, post_event) for _ in range(ITERATIONS)]
        list_lat = [_time_async_ms(mcp_server.list_skills) for _ in range(ITERATIONS)]
        read_lat = [_time_async_ms(mcp_server.read_skill, "mock_readonly") for _ in range(ITERATIONS)]

        cache = rt.indexer._cache
        hits, misses = cache.hits, cache.misses
        hit_rate = hits / (hits + misses) if (hits + misses) else 0.0

    rows = [
        _summarise("SessionStart hook", session_lat),
        _summarise("UserPromptSubmit hook", ups_lat),
        _summarise("PreToolUse hook", pre_lat),
        _summarise("PostToolUse hook", post_lat),
        _summarise("MCP list_skills", list_lat),
        _summarise("MCP read_skill", read_lat),
    ]

    print("# Phase 4 §4.7 micro-benchmark results\n")
    print(f"Iterations per path: {ITERATIONS}\n")
    print("| Path                         |    n |   median | p95 (ms) | max (ms) |")
    print("|------------------------------|-----:|---------:|---------:|---------:|")
    for row in rows:
        print(_format_row(row))
    print()
    print("## Skill-index cache\n")
    print(f"- hits: {hits}")
    print(f"- misses: {misses}")
    print(f"- hit_rate: {hit_rate * 100:.2f}%\n")

    print("## Targets vs measured")
    hook_ok = all(_percentile(s, 95) < 50 for s in (ups_lat, pre_lat, post_lat))
    mcp_ok = all(_percentile(s, 95) < 100 for s in (list_lat, read_lat))
    cache_ok = hit_rate > 0.95
    print(f"- hooks p95 < 50 ms: {'OK' if hook_ok else 'FAIL'}")
    print(f"- MCP p95 < 100 ms: {'OK' if mcp_ok else 'FAIL'}")
    print(f"- cache hit rate > 95 %: {'OK' if cache_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
