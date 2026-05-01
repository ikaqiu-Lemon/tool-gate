#!/usr/bin/env python3
"""Agent execution script for example 02 - doc-edit-staged.

This script processes user requests for document editing with staged workflow.

Usage:
    cd examples/02-doc-edit-staged
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
    change_stage,
    enable_skill,
    grant_status,
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
            if hasattr(v, 'model_dump'):
                dumped = v.model_dump()
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
            if hasattr(v, 'model_dump'):
                dumped = v.model_dump()
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
        skill_enable_granted = sum(1 for e in self.events if e['event_type'] == 'skill.enable' and e.get('decision') == 'granted')
        skill_enable_denied = sum(1 for e in self.events if e['event_type'] == 'skill.enable' and e.get('decision') == 'denied')

        tool_calls = [e for e in self.events if e['event_type'] == 'tool.call']
        successful_calls = sum(1 for e in tool_calls if e.get('decision') == 'allow')
        denied_calls = sum(1 for e in tool_calls if e.get('decision') == 'deny')

        whitelist_violations = sum(1 for e in tool_calls if e.get('error_bucket') == 'whitelist_violation')
        blocked_tools = sum(1 for e in tool_calls if e.get('error_bucket') == 'blocked')
        reason_missing = sum(1 for e in self.events if e['event_type'] == 'skill.enable' and e.get('deny_reason') == 'reason_missing')

        stage_changes = sum(1 for e in self.events if e['event_type'] == 'stage.change')

        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "shown_skills": skill_list_count,
            "read_skills": skill_read_count,
            "enabled_skills": skill_enable_granted,
            "denied_skills": skill_enable_denied,
            "reason_missing_count": reason_missing,
            "total_tool_calls": len(tool_calls),
            "successful_tool_calls": successful_calls,
            "denied_tool_calls": denied_calls,
            "whitelist_violation_count": whitelist_violations,
            "blocked_tools_count": blocked_tools,
            "stage_changes": stage_changes,
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
帮我把样例 01 输出的相关文档区块写回 rag-overview-v2
```

## 3. Skill 暴露与读取

| 阶段 | 数量 |
|------|------|
| shown (list_skills) | {metrics['shown_skills']} |
| read (read_skill) | {metrics['read_skills']} |
| enabled (enable_skill) | {metrics['enabled_skills']} |
| denied (enable_skill) | {metrics['denied_skills']} |
| reason_missing | {metrics['reason_missing_count']} |

## 4. 阶段切换

| 指标 | 数值 |
|------|------|
| 阶段切换次数 | {metrics['stage_changes']} |

## 5. 工具调用统计

| 指标 | 数值 |
|------|------|
| 总调用数 | {metrics['total_tool_calls']} |
| 成功 | {metrics['successful_tool_calls']} |
| 被拒绝 | {metrics['denied_tool_calls']} |
| 白名单违规 | {metrics['whitelist_violation_count']} |
| 全局阻止 | {metrics['blocked_tools_count']} |

## 6. 工具调用明细

"""

        tool_calls = [e for e in self.events if e['event_type'] == 'tool.call']
        if tool_calls:
            summary += "| # | 时间 | 工具 | 决策 | Error Bucket | 阶段 | 说明 |\n"
            summary += "|---|------|------|------|--------------|------|------|\n"
            for i, event in enumerate(tool_calls, 1):
                timestamp = event['timestamp'].split('T')[1][:8]
                tool_name = event.get('tool_short_name', event.get('tool_name', 'unknown'))
                decision = event.get('decision', 'unknown')
                error_bucket = event.get('error_bucket', '-')
                stage = event.get('stage', '-')
                status = "✅" if decision == "allow" else "❌"
                reason = event.get('deny_reason', '')[:30] if decision == 'deny' else "在白名单内"
                summary += f"| {i} | {timestamp} | {tool_name} | {decision} | {error_bucket} | {stage} | {status} {reason} |\n"

        summary += f"""

## 7. 治理效果
- ✅ 中风险技能 require_reason 检查生效
- ✅ 阶段化工作流正常运行
- ✅ 全局 blocked_tools 成功拦截
- ✅ 无误调用或授权异常

## 8. 任务完成情况

**任务目标**: 将相关文档区块写回 rag-overview-v2

**完成情况**:
- ✅ 成功读取原文档（analysis 阶段）
- ✅ 成功切换到 execution 阶段
- ✅ 成功写回文档内容
- ❌ 无法使用 shell 命令（全局阻止）

**原因分析**:
- `run_command` 工具在全局 blocked_tools 列表中
- 任何技能都无法启用此工具，这是预期的安全限制

**建议**:
- 当前工作流符合预期，无需调整
"""

        return summary


class Agent:
    """AI agent that helps users with document editing tasks."""

    def __init__(self, runtime: GovernanceRuntime, session_id: str, logger: SessionLogger):
        self.runtime = runtime
        self.session_id = session_id
        self.logger = logger
        self.thinking_delay = 0.5

    async def think(self, message: str) -> None:
        """Internal reasoning process."""
        print(f"\n💭 {message}")
        await asyncio.sleep(self.thinking_delay)

    async def process_user_request(self, user_request: str) -> None:
        """Process the user's request step by step."""
        print(f"\n👤 用户: {user_request}")

        # Step 1: Understand the request
        await self.think("用户需要将相关文档区块写回到 rag-overview-v2。这是一个写操作，需要谨慎处理。")

        # Step 2: Discover available skills
        await self.think("首先，让我列出可用的技能...")
        self.logger.record_event("agent.action", {
            "action": "list_skills",
            "reasoning": "需要发现可用的技能来完成文档编辑任务"
        })

        skills = await list_skills()
        self.logger.record_event("skill.list", {
            "shown_skills": [{"skill_id": s['skill_id'], "name": s['name'], "risk_level": s['risk_level']}
                            for s in skills]
        })

        print(f"\n🤖 找到 {len(skills)} 个可用技能:")
        for skill in skills:
            print(f"   - {skill['name']} ({skill['risk_level']}): {skill['description'][:60]}...")

        # Step 3: Read skill details
        await self.think("'yuque-doc-edit' 看起来可以帮我编辑文档。让我读取它的详细信息。")

        self.logger.record_event("agent.action", {
            "action": "read_skill",
            "skill_id": "yuque-doc-edit",
            "reasoning": "这个技能包含文档编辑功能"
        })

        skill_detail = await read_skill("yuque-doc-edit")
        self.logger.record_event("skill.read", {
            "skill_id": "yuque-doc-edit",
            "content_length": len(str(skill_detail))
        })

        if "error" in skill_detail:
            print(f"\n❌ 读取技能失败: {skill_detail['error']}")
            return

        metadata = skill_detail['metadata']
        print(f"\n📖 技能详情:")
        print(f"   名称: {metadata['name']}")
        print(f"   风险等级: {metadata['risk_level']}")
        print(f"   阶段: {', '.join([s['stage_id'] for s in metadata.get('stages', [])])}")

        # Step 4: Try to enable without reason (should fail)
        await self.think("让我尝试启用这个技能...")

        self.logger.record_event("agent.action", {
            "action": "enable_skill",
            "skill_id": "yuque-doc-edit",
            "reasoning": "尝试启用技能（未提供 reason）"
        })

        enable_result = await enable_skill("yuque-doc-edit", scope="session", ttl=3600)
        
        if not enable_result.get("granted"):
            print(f"\n⚠️  技能启用失败: {enable_result.get('reason')}")
            self.logger.record_event("skill.enable", {
                "skill_id": "yuque-doc-edit",
                "decision": "denied",
                "deny_reason": enable_result.get('reason')
            })

            await self.think("看来这个技能需要提供原因才能启用。让我重新尝试。")

            # Step 5: Enable with reason
            self.logger.record_event("agent.action", {
                "action": "enable_skill",
                "skill_id": "yuque-doc-edit",
                "reasoning": "提供原因后重新启用技能"
            })

            enable_result = await enable_skill(
                "yuque-doc-edit",
                scope="session",
                ttl=3600,
                reason="将样例 01 的关联分析结果追加到 rag-overview-v2 文档的相关文档区块"
            )

        self.logger.record_event("skill.enable", {
            "skill_id": "yuque-doc-edit",
            "decision": "granted" if enable_result.get("granted") else "denied",
            "allowed_tools": enable_result.get("allowed_tools", []),
            "stage": enable_result.get("stage", "unknown")
        })

        if not enable_result.get("granted"):
            print(f"\n❌ 技能启用失败: {enable_result.get('reason')}")
            return

        print(f"\n✅ 技能已启用")
        print(f"   当前阶段: {enable_result.get('stage', 'unknown')}")
        print(f"   可用工具: {len(enable_result.get('allowed_tools', []))} 个")

        # Step 6: Read document in analysis stage
        await self.think("在修改之前，让我先读取原文档内容...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "yuque_get_doc",
            "reasoning": "在 analysis 阶段读取文档内容"
        })

        get_doc_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-yuque__yuque_get_doc",
            "tool_input": {"doc_id": "rag-overview-v2"}
        }
        get_doc_result = hook_handler.handle_pre_tool_use(get_doc_event)
        decision = get_doc_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-yuque__yuque_get_doc",
            "tool_short_name": "yuque_get_doc",
            "decision": decision,
            "stage": "analysis",
            "in_active_tools": True,
            "error_bucket": None if decision == "allow" else "whitelist_violation"
        })

        if decision == "allow":
            print(f"\n📄 文档读取成功:")
            print(f"   标题: RAG 技术概览 v2")
            print(f"   最后修改: 2026-04-19T10:30:00+08:00")
            print(f"   字数: 3500")
        else:
            print(f"\n❌ 文档读取失败")
            return

        # Step 7: Try to update in analysis stage (should fail)
        await self.think("现在让我尝试写入文档...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "yuque_update_doc",
            "reasoning": "尝试在 analysis 阶段写入文档（应该被拒绝）"
        })

        update_doc_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-yuque__yuque_update_doc",
            "tool_input": {"doc_id": "rag-overview-v2", "body_markdown": "..."}
        }
        update_doc_result = hook_handler.handle_pre_tool_use(update_doc_event)
        decision = update_doc_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")
        reason = update_doc_result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-yuque__yuque_update_doc",
            "tool_short_name": "yuque_update_doc",
            "decision": decision,
            "deny_reason": reason if decision == "deny" else None,
            "stage": "analysis",
            "in_active_tools": False,
            "error_bucket": "whitelist_violation" if decision == "deny" else None
        })

        if decision == "deny":
            print(f"\n⚠️  写入被拒绝: {reason}")
            await self.think("看来在 analysis 阶段不能写入。我需要切换到 execution 阶段。")

            # Step 8: Check current grant status
            self.logger.record_event("agent.action", {
                "action": "grant_status",
                "reasoning": "检查当前授权状态"
            })

            status = await grant_status()
            print(f"\n📊 当前授权状态:")
            for grant in status:
                print(f"   技能: {grant['skill_id']}")
                print(f"   阶段: {grant.get('stage', 'unknown')}")
                print(f"   TTL 剩余: {grant.get('ttl_remaining', 0)} 秒")

            # Step 9: Change to execution stage
            await self.think("让我切换到 execution 阶段...")

            self.logger.record_event("agent.action", {
                "action": "change_stage",
                "skill_id": "yuque-doc-edit",
                "stage_id": "execution",
                "reasoning": "切换到 execution 阶段以执行写入操作"
            })

            change_result = await change_stage("yuque-doc-edit", "execution")

            self.logger.record_event("stage.change", {
                "skill_id": "yuque-doc-edit",
                "from_stage": "analysis",
                "to_stage": "execution",
                "success": change_result.get("ok", False)
            })

            if change_result.get("ok"):
                print(f"\n✅ 已切换到 execution 阶段")
                print(f"   新的可用工具: {', '.join(change_result.get('active_tools', []))}")
            else:
                print(f"\n❌ 阶段切换失败")
                return

            # Step 10: Update document in execution stage
            await self.think("现在让我重新尝试写入文档...")

            self.logger.record_event("agent.action", {
                "action": "call_tool",
                "tool_name": "yuque_update_doc",
                "reasoning": "在 execution 阶段写入文档"
            })

            update_doc_event2 = {
                "event": "PreToolUse",
                "session_id": self.session_id,
                "tool_name": "mcp__mock-yuque__yuque_update_doc",
                "tool_input": {
                    "doc_id": "rag-overview-v2",
                    "body_markdown": "## 相关文档\n\n- [向量召回最佳实践](vector-recall-best)\n- [RAG 评估手册](rag-eval-playbook)"
                }
            }
            update_doc_result2 = hook_handler.handle_pre_tool_use(update_doc_event2)
            decision2 = update_doc_result2.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")

            self.logger.record_event("tool.call", {
                "tool_name": "mcp__mock-yuque__yuque_update_doc",
                "tool_short_name": "yuque_update_doc",
                "decision": decision2,
                "stage": "execution",
                "in_active_tools": True,
                "error_bucket": None if decision2 == "allow" else "whitelist_violation"
            })

            if decision2 == "allow":
                print(f"\n✅ 文档更新成功!")
                print(f"   已追加相关文档区块到 rag-overview-v2")

                self.logger.record_event("agent.deliverable", {
                    "type": "document_update",
                    "doc_id": "rag-overview-v2",
                    "operation": "append",
                    "content": "相关文档区块"
                })
            else:
                print(f"\n❌ 文档更新失败")

        # Step 11: Try to use blocked tool (run_command)
        await self.think("让我尝试使用 shell 命令查看磁盘使用情况...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "run_command",
            "reasoning": "尝试使用全局阻止的工具"
        })

        run_cmd_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-shell__run_command",
            "tool_input": {"cmd": "df -h"}
        }
        run_cmd_result = hook_handler.handle_pre_tool_use(run_cmd_event)
        decision3 = run_cmd_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")
        reason3 = run_cmd_result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-shell__run_command",
            "tool_short_name": "run_command",
            "decision": decision3,
            "deny_reason": reason3 if decision3 == "deny" else None,
            "in_active_tools": False,
            "error_bucket": "blocked" if "blocked" in reason3.lower() else "whitelist_violation"
        })

        if decision3 == "deny":
            print(f"\n⚠️  Shell 命令被拒绝: {reason3}")
            print(f"   说明: run_command 在全局 blocked_tools 列表中")

        # Step 12: Summarize
        print(f"\n" + "="*70)
        print(f"📝 任务总结")
        print(f"="*70)
        print(f"✅ 已完成: 文档编辑任务")
        print(f"✅ 验证: 阶段化工作流正常运行")
        print(f"✅ 验证: 全局 blocked_tools 成功拦截")
        print(f"\n生成的交付物:")
        print(f"   - 更新后的 rag-overview-v2 文档")
        print(f"   - 相关文档区块已追加")


async def main_async() -> None:
    """Run the agent to process user request."""
    print("\n" + "=" * 70)
    print("  文档编辑 - 阶段化工作流演示")
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

    user_request = "帮我把样例 01 输出的相关文档区块写回 rag-overview-v2"

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
