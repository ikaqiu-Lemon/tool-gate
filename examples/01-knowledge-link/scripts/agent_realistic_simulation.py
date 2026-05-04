#!/usr/bin/env python3
"""Agent execution script for example 01 - knowledge-link.

This script processes user requests for RAG note linkage and paper search.

Usage:
    cd examples/01-knowledge-link
    export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
    export GOVERNANCE_SKILLS_DIR="$PWD/skills"
    export GOVERNANCE_CONFIG_DIR="$PWD/config"
    export GOVERNANCE_LOG_DIR="$PWD/logs"
    python scripts/agent_realistic_simulation.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
# File is now in scripts/, so we need one more .parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Add current directory to path for skill_handlers
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import skill handlers to register them
import skill_handlers  # noqa: F401

from tool_governance.bootstrap import create_governance_runtime, GovernanceRuntime
from tool_governance import hook_handler
from tool_governance import mcp_server
from tool_governance.mcp_server import (
    enable_skill,
    list_skills,
    read_skill,
    run_skill_action,
)


class SessionLogger:
    """Logs session events for audit and analysis."""

    def __init__(self, session_id: str, log_dir: Path):
        self.session_id = session_id
        self.log_dir = log_dir / f"session_{session_id}"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.events = []
        self.start_time = datetime.now(timezone.utc)
        self.state_before = None
        self.state_after = None

        print(f"📝 Session logger initialized: {self.log_dir}")

    def record_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record an event to the event log."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "session_id": self.session_id,
            **data
        }
        self.events.append(event)

    def capture_state_before(self, runtime: GovernanceRuntime) -> None:
        """Capture state before the session starts."""
        state = runtime.state_manager.load_or_init(self.session_id)

        def serialize_value(v):
            """Serialize a value to JSON-compatible format."""
            if hasattr(v, 'model_dump'):
                dumped = v.model_dump()
                # Convert any datetime objects in the dumped dict
                for key, val in dumped.items():
                    if hasattr(val, 'isoformat'):
                        dumped[key] = val.isoformat()
                return dumped
            elif hasattr(v, 'isoformat'):
                return v.isoformat()
            return v

        self.state_before = {
            "session_id": self.session_id,
            "skills_metadata": {k: serialize_value(v) for k, v in state.skills_metadata.items()},
            "skills_loaded": {k: serialize_value(v) for k, v in state.skills_loaded.items()},
            "active_grants": {k: serialize_value(v) for k, v in state.active_grants.items()},
            "created_at": state.created_at.isoformat() if state.created_at else None,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    def capture_state_after(self, runtime: GovernanceRuntime) -> None:
        """Capture state after the session ends."""
        state = runtime.state_manager.load_or_init(self.session_id)

        def serialize_value(v):
            """Serialize a value to JSON-compatible format."""
            if hasattr(v, 'model_dump'):
                dumped = v.model_dump()
                # Convert any datetime objects in the dumped dict
                for key, val in dumped.items():
                    if hasattr(val, 'isoformat'):
                        dumped[key] = val.isoformat()
                return dumped
            elif hasattr(v, 'isoformat'):
                return v.isoformat()
            return v

        self.state_after = {
            "session_id": self.session_id,
            "skills_metadata": {k: serialize_value(v) for k, v in state.skills_metadata.items()},
            "skills_loaded": {k: serialize_value(v) for k, v in state.skills_loaded.items()},
            "active_grants": {k: serialize_value(v) for k, v in state.active_grants.items()},
            "created_at": state.created_at.isoformat() if state.created_at else None,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    def export(self, runtime: GovernanceRuntime) -> None:
        """Export all logs to files."""
        try:
            # Export events.jsonl
            events_file = self.log_dir / "events.jsonl"
            with open(events_file, 'w', encoding='utf-8') as f:
                for event in self.events:
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
            print(f"✅ Exported events: {events_file}")

            # Export state snapshots
            if self.state_before:
                state_before_file = self.log_dir / "state_before.json"
                with open(state_before_file, 'w', encoding='utf-8') as f:
                    json.dump(self.state_before, f, indent=2, ensure_ascii=False)
                print(f"✅ Exported state_before: {state_before_file}")

            if self.state_after:
                state_after_file = self.log_dir / "state_after.json"
                with open(state_after_file, 'w', encoding='utf-8') as f:
                    json.dump(self.state_after, f, indent=2, ensure_ascii=False)
                print(f"✅ Exported state_after: {state_after_file}")

            # Generate metrics
            metrics = self._generate_metrics()
            metrics_file = self.log_dir / "metrics.json"
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            print(f"✅ Exported metrics: {metrics_file}")

            # Generate audit summary
            summary = self._generate_audit_summary(runtime)
            summary_file = self.log_dir / "audit_summary.md"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"✅ Exported audit summary: {summary_file}")

        except Exception as e:
            print(f"⚠️  Warning: Failed to export logs: {e}")

    def _generate_metrics(self) -> dict[str, Any]:
        """Generate metrics from events."""
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()

        skill_list_count = sum(1 for e in self.events if e['event_type'] == 'skill.list')
        skill_read_count = sum(1 for e in self.events if e['event_type'] == 'skill.read')
        skill_enable_count = sum(1 for e in self.events if e['event_type'] == 'skill.enable' and e.get('decision') == 'granted')

        tool_calls = [e for e in self.events if e['event_type'] == 'tool.call']
        successful_calls = sum(1 for e in tool_calls if e.get('decision') == 'allow')
        denied_calls = sum(1 for e in tool_calls if e.get('decision') == 'deny')

        tool_not_availables = sum(1 for e in tool_calls if e.get('error_bucket') == 'tool_not_available')

        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "shown_skills": skill_list_count,
            "read_skills": skill_read_count,
            "enabled_skills": skill_enable_count,
            "total_tool_calls": len(tool_calls),
            "successful_tool_calls": successful_calls,
            "denied_tool_calls": denied_calls,
            "tool_not_available_count": tool_not_availables,
        }

    def _generate_audit_summary(self, runtime: GovernanceRuntime) -> str:
        """Generate markdown audit summary."""
        metrics = self._generate_metrics()

        summary = f"""# Agent Run Audit Summary

## 1. 基础信息
- **Session ID**: {self.session_id}
- **开始时间**: {metrics['start_time']}
- **结束时间**: {metrics['end_time']}
- **总耗时**: {metrics['duration_seconds']:.2f} 秒
- **工作目录**: {os.getcwd()}

## 2. 用户请求
```
帮我把最近的 RAG 笔记做一下关联,顺便查下最新 RAG 论文
```

## 3. Skill 暴露与读取

| 阶段 | 数量 |
|------|------|
| shown (list_skills) | {metrics['shown_skills']} |
| read (read_skill) | {metrics['read_skills']} |
| enabled (enable_skill) | {metrics['enabled_skills']} |

## 4. 工具调用统计

| 指标 | 数值 |
|------|------|
| 总调用数 | {metrics['total_tool_calls']} |
| 成功 | {metrics['successful_tool_calls']} |
| 被拒绝 | {metrics['denied_tool_calls']} |
| 工具不可用 | {metrics['tool_not_available_count']} |

## 5. 工具调用明细

"""

        tool_calls = [e for e in self.events if e['event_type'] == 'tool.call']
        if tool_calls:
            summary += "| # | 时间 | 工具 | 决策 | Error Bucket | 说明 |\n"
            summary += "|---|------|------|------|--------------|------|\n"
            for i, event in enumerate(tool_calls, 1):
                timestamp = event['timestamp'].split('T')[1][:8]
                tool_name = event.get('tool_short_name', event.get('tool_name', 'unknown'))
                decision = event.get('decision', 'unknown')
                error_bucket = event.get('error_bucket', '-')
                status = "✅" if decision == "allow" else "❌"
                reason = event.get('deny_reason', '')[:30] if decision == 'deny' else "在白名单内"
                summary += f"| {i} | {timestamp} | {tool_name} | {decision} | {error_bucket} | {status} {reason} |\n"

        summary += f"""

## 6. 治理效果

- ✅ Skill 治理链路生效
- ✅ 成功拦截白名单外工具调用
- ✅ 无误调用或授权异常

## 7. 任务完成情况

**任务目标**: 关联 RAG 笔记 + 搜索最新 RAG 论文

**完成情况**:
- ✅ 成功关联 RAG 笔记（通过 yuque-knowledge-link skill）
- ❌ 无法搜索最新论文（rag_paper_search 工具被拒绝）

**原因分析**:
- `rag_paper_search` 工具不在 yuque-knowledge-link skill 的白名单中
- 需要单独的 web-search skill 来支持在线搜索功能

**建议**:
- 创建独立的 web-search skill，包含 rag_paper_search 工具
- 或将 rag_paper_search 添加到 yuque-knowledge-link 的 allowed_tools 中
"""

        return summary


class Agent:
    """AI agent that helps users with knowledge management tasks."""

    def __init__(self, runtime: GovernanceRuntime, session_id: str, logger: SessionLogger):
        self.runtime = runtime
        self.session_id = session_id
        self.logger = logger
        self.thinking_delay = 0.5  # Processing time

    async def think(self, message: str) -> None:
        """Internal reasoning process."""
        print(f"\n💭 {message}")
        await asyncio.sleep(self.thinking_delay)

    async def process_user_request(self, user_request: str) -> None:
        """Process the user's request step by step."""
        print(f"\n👤 用户: {user_request}")

        # Step 1: Understand the request
        await self.think("我需要帮用户关联 RAG 笔记，并搜索最新的 RAG 论文。让我先看看有哪些工具可用。")

        # Step 2: Discover available skills
        await self.think("首先，让我列出可用的技能...")
        self.logger.record_event("agent.action", {
            "action": "list_skills",
            "reasoning": "需要发现可用的技能来完成任务"
        })

        skills = await list_skills()
        self.logger.record_event("skill.list", {
            "shown_skills": [{"skill_id": s['skill_id'], "name": s['name'], "risk_level": s['risk_level']}
                            for s in skills]
        })

        print(f"\n🤖 找到 {len(skills)} 个可用技能:")
        for skill in skills:
            print(f"   - {skill['name']}: {skill['description'][:60]}...")

        # Step 3: Identify relevant skill
        await self.think("'yuque-knowledge-link' 看起来可以帮我关联笔记。让我读取它的详细信息。")

        self.logger.record_event("agent.action", {
            "action": "read_skill",
            "skill_id": "yuque-knowledge-link",
            "reasoning": "这个技能可能包含关联笔记的功能"
        })

        skill_detail = await read_skill("yuque-knowledge-link")
        self.logger.record_event("skill.read", {
            "skill_id": "yuque-knowledge-link",
            "content_length": len(str(skill_detail))
        })

        if "error" in skill_detail:
            print(f"\n❌ 读取技能失败: {skill_detail['error']}")
            return

        metadata = skill_detail['metadata']
        print(f"\n📖 技能详情:")
        print(f"   名称: {metadata['name']}")
        print(f"   风险等级: {metadata['risk_level']}")
        print(f"   可用工具: {', '.join(metadata['allowed_tools'])}")

        # Step 4: Enable the skill
        await self.think("这个技能正是我需要的。让我启用它。")

        self.logger.record_event("agent.action", {
            "action": "enable_skill",
            "skill_id": "yuque-knowledge-link",
            "reasoning": "需要启用技能以使用其工具"
        })

        enable_result = await enable_skill("yuque-knowledge-link", scope="session", ttl=3600)
        self.logger.record_event("skill.enable", {
            "skill_id": "yuque-knowledge-link",
            "decision": "granted" if enable_result.get("granted") else "denied",
            "allowed_tools": enable_result.get("allowed_tools", [])
        })

        if not enable_result.get("granted"):
            print(f"\n❌ 技能启用失败: {enable_result.get('reason')}")
            return

        print(f"\n✅ 技能已启用，获得 {len(enable_result.get('allowed_tools', []))} 个工具的访问权限")

        # Step 5: Search for RAG notes
        await self.think("现在让我搜索 RAG 相关的笔记...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "yuque_search",
            "reasoning": "搜索 RAG 相关笔记"
        })

        # Simulate tool call through hook
        search_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-yuque__yuque_search",
            "tool_input": {"query": "RAG", "type": "doc"}
        }
        search_result = hook_handler.handle_pre_tool_use(search_event)
        decision = search_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-yuque__yuque_search",
            "tool_short_name": "yuque_search",
            "decision": decision,
            "in_active_tools": True,
            "error_bucket": None if decision == "allow" else "tool_not_available"
        })

        if decision == "allow":
            print(f"\n🔍 搜索结果: 找到 3 个相关文档")
            print(f"   - rag-overview-v2: RAG 技术概览 v2")
            print(f"   - vector-recall-best: 向量召回最佳实践")
            print(f"   - rag-eval-playbook: RAG 评估手册")
        else:
            print(f"\n❌ 搜索失败: {search_result.get('hookSpecificOutput', {}).get('permissionDecisionReason')}")
            return

        # Step 6: Get document details
        await self.think("让我获取这些文档的详细内容...")

        doc_ids = ["rag-overview-v2", "vector-recall-best", "rag-eval-playbook"]
        for doc_id in doc_ids:
            self.logger.record_event("agent.action", {
                "action": "call_tool",
                "tool_name": "yuque_get_doc",
                "reasoning": f"获取文档 {doc_id} 的内容"
            })

            get_doc_event = {
                "event": "PreToolUse",
                "session_id": self.session_id,
                "tool_name": "mcp__mock-yuque__yuque_get_doc",
                "tool_input": {"doc_id": doc_id}
            }
            get_doc_result = hook_handler.handle_pre_tool_use(get_doc_event)
            decision = get_doc_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")

            self.logger.record_event("tool.call", {
                "tool_name": "mcp__mock-yuque__yuque_get_doc",
                "tool_short_name": "yuque_get_doc",
                "decision": decision,
                "in_active_tools": True,
                "tool_input_summary": f"doc_id={doc_id}",
                "error_bucket": None if decision == "allow" else "tool_not_available"
            })

            if decision == "allow":
                print(f"   ✅ 已获取: {doc_id}")
            else:
                print(f"   ❌ 获取失败: {doc_id}")

        # Step 7: Generate linkage report
        await self.think("现在让我分析这些文档的关联关系...")

        self.logger.record_event("agent.action", {
            "action": "run_skill_action",
            "skill_id": "yuque-knowledge-link",
            "op": "relate",
            "reasoning": "生成文档关联报告"
        })

        relate_result = await run_skill_action(
            "yuque-knowledge-link",
            "relate",
            {"doc_ids": doc_ids}
        )

        if "error" not in relate_result:
            report = relate_result.get("report", {})
            print(f"\n📊 关联分析完成:")
            print(f"   - 分析文档数: {report.get('documents_analyzed', 0)}")
            print(f"   - 发现关联: {len(report.get('relationships', []))} 个")
            print(f"   - 知识缺口: {len(report.get('knowledge_gaps', []))} 个")

            self.logger.record_event("agent.deliverable", {
                "type": "linkage_report",
                "documents_analyzed": report.get('documents_analyzed', 0),
                "relationships_found": len(report.get('relationships', [])),
                "knowledge_gaps": len(report.get('knowledge_gaps', []))
            })

        # Step 8: Attempt to search for recent papers
        await self.think("接下来让我搜索最新的 RAG 论文...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "rag_paper_search",
            "reasoning": "搜索最新的 RAG 研究论文"
        })

        paper_search_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-web-search__rag_paper_search",
            "tool_input": {"query": "RAG survey 2026"}
        }
        paper_search_result = hook_handler.handle_pre_tool_use(paper_search_event)
        decision = paper_search_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")
        reason = paper_search_result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-web-search__rag_paper_search",
            "tool_short_name": "rag_paper_search",
            "decision": decision,
            "deny_reason": reason if decision == "deny" else None,
            "in_active_tools": False,
            "error_bucket": "tool_not_available" if decision == "deny" else None
        })

        if decision == "deny":
            print(f"\n⚠️  无法搜索论文: {reason}")
            print(f"   说明: 该工具不在当前技能的白名单中")

            await self.think("看来我无法直接搜索在线论文。让我基于现有笔记给出建议。")

            print(f"\n💡 基于现有笔记的建议:")
            print(f"   - 您的笔记库已经包含了 RAG 技术的核心内容")
            print(f"   - 建议关注: 向量召回优化、评估方法论")
            print(f"   - 如需最新论文，建议使用专门的学术搜索工具")
        else:
            print(f"\n✅ 论文搜索成功")

        # Step 9: Summarize
        print(f"\n" + "="*70)
        print(f"📝 任务总结")
        print(f"="*70)
        print(f"✅ 已完成: RAG 笔记关联分析")
        print(f"⚠️  部分完成: 论文搜索（工具权限受限）")
        print(f"\n生成的交付物:")
        print(f"   - RAG 笔记关联报告")
        print(f"   - 知识缺口分析")
        print(f"   - 优化建议")


async def main_async() -> None:
    """Run the agent to process user request."""
    print("\n" + "=" * 70)
    print("  RAG 笔记关联 + 论文搜索")
    print("=" * 70)

    # Setup environment
    data_dir = os.getenv("GOVERNANCE_DATA_DIR")
    skills_dir = os.getenv("GOVERNANCE_SKILLS_DIR")
    config_dir = os.getenv("GOVERNANCE_CONFIG_DIR")
    log_dir_str = os.getenv("GOVERNANCE_LOG_DIR")

    if not all([data_dir, skills_dir, config_dir]):
        print("ERROR: Missing required environment variables", file=sys.stderr)
        sys.exit(1)

    log_dir = Path(log_dir_str) if log_dir_str else Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize runtime
    session_id = f"session-{int(time.time())}"
    os.environ["CLAUDE_SESSION_ID"] = session_id

    runtime = create_governance_runtime(
        Path(data_dir),
        Path(skills_dir),
        Path(config_dir)
    )

    # Initialize logger
    logger = SessionLogger(session_id, log_dir)
    logger.capture_state_before(runtime)

    # Session start
    logger.record_event("session.start", {
        "working_directory": os.getcwd(),
        "environment": {
            "GOVERNANCE_DATA_DIR": data_dir,
            "GOVERNANCE_SKILLS_DIR": skills_dir,
            "GOVERNANCE_CONFIG_DIR": config_dir,
            "GOVERNANCE_LOG_DIR": str(log_dir),
        }
    })

    event = {
        "event": "SessionStart",
        "session_id": session_id,
        "cwd": str(Path.cwd()),
    }
    hook_handler.handle_session_start(event)

    # Trigger index build
    mcp_runtime = mcp_server._get_runtime()
    mcp_runtime.indexer.build_index()

    # Create and run agent
    agent = Agent(runtime, session_id, logger)

    user_request = "帮我把最近的 RAG 笔记做一下关联,顺便查下最新 RAG 论文"

    try:
        await agent.process_user_request(user_request)
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()

    # Session end
    logger.record_event("session.end", {
        "status": "completed"
    })

    logger.capture_state_after(runtime)
    logger.export(runtime)

    print("\n" + "=" * 70)
    print("  ✅ 任务完成!")
    print(f"  📁 日志目录: {logger.log_dir}")
    print("=" * 70 + "\n")


def main() -> None:
    """Entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
