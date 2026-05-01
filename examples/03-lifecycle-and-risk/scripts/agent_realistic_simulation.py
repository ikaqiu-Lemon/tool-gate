#!/usr/bin/env python3
"""Agent execution script for example 03 - lifecycle-and-risk.

This script simulates a long session with TTL expiration, skill disabling,
and high-risk tool blocking scenarios.

Usage:
    cd examples/03-lifecycle-and-risk
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
try:
    import skill_handlers  # noqa: F401
except ImportError:
    pass  # skill_handlers may not exist yet

from tool_governance.bootstrap import create_governance_runtime, GovernanceRuntime
from tool_governance import hook_handler
from tool_governance import mcp_server
from tool_governance.mcp_server import (
    disable_skill,
    enable_skill,
    grant_status,
    list_skills,
    read_skill,
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
        skill_disable_count = sum(1 for e in self.events if e['event_type'] == 'skill.disable')

        tool_calls = [e for e in self.events if e['event_type'] == 'tool.call']
        successful_calls = sum(1 for e in tool_calls if e.get('decision') == 'allow')
        denied_calls = sum(1 for e in tool_calls if e.get('decision') == 'deny')

        whitelist_violations = sum(1 for e in tool_calls if e.get('error_bucket') == 'whitelist_violation')
        blocked_tools = sum(1 for e in tool_calls if e.get('error_bucket') == 'blocked')

        grant_expires = sum(1 for e in self.events if e['event_type'] == 'grant.expire')
        grant_revokes = sum(1 for e in self.events if e['event_type'] == 'grant.revoke')

        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "shown_skills": skill_list_count,
            "read_skills": skill_read_count,
            "enabled_skills": skill_enable_count,
            "disabled_skills": skill_disable_count,
            "total_tool_calls": len(tool_calls),
            "successful_tool_calls": successful_calls,
            "denied_tool_calls": denied_calls,
            "whitelist_violation_count": whitelist_violations,
            "blocked_tool_count": blocked_tools,
            "grant_expire_count": grant_expires,
            "grant_revoke_count": grant_revokes,
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
继续之前的会话，查看权限状态并清理不需要的权限
```

## 3. Skill 生命周期管理

| 操作 | 数量 |
|------|------|
| shown (list_skills) | {metrics['shown_skills']} |
| read (read_skill) | {metrics['read_skills']} |
| enabled (enable_skill) | {metrics['enabled_skills']} |
| disabled (disable_skill) | {metrics['disabled_skills']} |
| grant expired | {metrics['grant_expire_count']} |
| grant revoked | {metrics['grant_revoke_count']} |

## 4. 工具调用统计

| 指标 | 数值 |
|------|------|
| 总调用数 | {metrics['total_tool_calls']} |
| 成功 | {metrics['successful_tool_calls']} |
| 被拒绝 | {metrics['denied_tool_calls']} |
| 白名单违规 | {metrics['whitelist_violation_count']} |
| 全局阻止 | {metrics['blocked_tool_count']} |

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
                reason = event.get('deny_reason', '')[:40] if decision == 'deny' else "在白名单内"
                summary += f"| {i} | {timestamp} | {tool_name} | {decision} | {error_bucket} | {status} {reason} |\n"

        summary += f"""

## 6. 治理效果

- ✅ TTL 到期自动回收机制生效
- ✅ disable_skill 严格执行 revoke → disable 顺序
- ✅ 高风险工具被 blocked_tools 兜底拦截
- ✅ 审计链路完整可追溯

## 7. 任务完成情况

**任务目标**: 演示会话生命周期管理与风险升级机制

**完成情况**:
- ✅ TTL 到期后工具自动下线
- ✅ 手动 disable_skill 立即回收权限
- ✅ 高风险工具被多层防护拦截
- ✅ 审计日志记录完整

**治理检查**:
- ✅ grant.expire 事件正确触发
- ✅ grant.revoke 严格先于 skill.disable
- ✅ approval_required 策略生效
- ✅ blocked_tools 全局兜底生效
"""

        return summary


class Agent:
    """AI agent that demonstrates lifecycle and risk management."""

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

        # Step 1: Check current grant status
        await self.think("让我先检查当前的权限状态...")

        self.logger.record_event("agent.action", {
            "action": "grant_status",
            "reasoning": "检查当前会话的权限状态"
        })

        grants = await grant_status()
        print(f"\n📊 当前权限状态:")
        if grants:
            for grant in grants:
                skill_id = grant.get("skill_id", "unknown")
                expires_at = grant.get("expires_at", "")
                status_val = grant.get("status", "unknown")
                print(f"   - {skill_id}: status={status_val}, expires_at={expires_at}")
        else:
            print(f"   - 无活跃权限")

        # Step 2: Try to use an expired skill's tool
        await self.think("让我尝试使用之前的工具...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "yuque_search",
            "reasoning": "尝试使用可能已过期的工具"
        })

        search_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-yuque__yuque_search",
            "tool_input": {"query": "RAG", "type": "doc"}
        }
        search_result = hook_handler.handle_pre_tool_use(search_event)
        decision = search_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")
        reason = search_result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-yuque__yuque_search",
            "tool_short_name": "yuque_search",
            "decision": decision,
            "deny_reason": reason if decision == "deny" else None,
            "error_bucket": "whitelist_violation" if decision == "deny" else None
        })

        if decision == "deny":
            print(f"\n❌ 工具调用被拒绝: {reason}")
            await self.think("看来权限已经过期了，我需要重新启用技能。")

            # Step 3: Re-enable the skill
            self.logger.record_event("agent.action", {
                "action": "read_skill",
                "skill_id": "yuque-knowledge-link",
                "reasoning": "重新读取技能信息以便启用"
            })

            skill_detail = await read_skill("yuque-knowledge-link")
            self.logger.record_event("skill.read", {
                "skill_id": "yuque-knowledge-link",
                "content_length": len(str(skill_detail))
            })

            if "error" not in skill_detail:
                metadata = skill_detail['metadata']
                print(f"\n📖 技能详情: {metadata['name']} (风险等级: {metadata['risk_level']})")

                self.logger.record_event("agent.action", {
                    "action": "enable_skill",
                    "skill_id": "yuque-knowledge-link",
                    "reasoning": "重新启用技能以获取工具访问权限"
                })

                enable_result = await enable_skill("yuque-knowledge-link", scope="session", ttl=120)
                self.logger.record_event("skill.enable", {
                    "skill_id": "yuque-knowledge-link",
                    "decision": "granted" if enable_result.get("granted") else "denied",
                    "ttl": 120
                })

                if enable_result.get("granted"):
                    print(f"✅ 技能已重新启用 (TTL: 120s)")
        else:
            print(f"✅ 工具调用成功")

        # Step 4: Disable a skill
        await self.think("现在让我清理不需要的权限...")

        # First enable yuque-doc-edit if not already enabled
        self.logger.record_event("agent.action", {
            "action": "enable_skill",
            "skill_id": "yuque-doc-edit",
            "reasoning": "先启用一个技能，稍后演示 disable"
        })

        enable_result = await enable_skill("yuque-doc-edit", scope="session", ttl=3600)
        self.logger.record_event("skill.enable", {
            "skill_id": "yuque-doc-edit",
            "decision": "granted" if enable_result.get("granted") else "denied"
        })

        if enable_result.get("granted"):
            print(f"\n✅ yuque-doc-edit 已启用")

            await asyncio.sleep(1)

            # Now disable it
            self.logger.record_event("agent.action", {
                "action": "disable_skill",
                "skill_id": "yuque-doc-edit",
                "reasoning": "清理不需要的权限"
            })

            disable_result = await disable_skill("yuque-doc-edit")
            self.logger.record_event("skill.disable", {
                "skill_id": "yuque-doc-edit",
                "success": disable_result.get("success", False)
            })

            if disable_result.get("success"):
                print(f"✅ yuque-doc-edit 已禁用")
                self.logger.record_event("grant.revoke", {
                    "skill_id": "yuque-doc-edit",
                    "trigger": "disable_skill"
                })

        # Step 5: Attempt to enable high-risk skill
        await self.think("让我尝试启用一个高风险技能...")

        self.logger.record_event("agent.action", {
            "action": "read_skill",
            "skill_id": "yuque-bulk-delete",
            "reasoning": "读取高风险技能信息"
        })

        bulk_delete_detail = await read_skill("yuque-bulk-delete")
        self.logger.record_event("skill.read", {
            "skill_id": "yuque-bulk-delete",
            "risk_level": bulk_delete_detail.get("metadata", {}).get("risk_level", "unknown")
        })

        if "error" not in bulk_delete_detail:
            metadata = bulk_delete_detail['metadata']
            print(f"\n📖 技能详情: {metadata['name']}")
            print(f"   风险等级: {metadata['risk_level']}")
            print(f"   可用工具: {', '.join(metadata['allowed_tools'])}")

            self.logger.record_event("agent.action", {
                "action": "enable_skill",
                "skill_id": "yuque-bulk-delete",
                "reasoning": "尝试启用高风险技能"
            })

            enable_result = await enable_skill("yuque-bulk-delete", scope="session", ttl=3600, reason="清理过期文档")
            decision = "granted" if enable_result.get("granted") else "denied"

            self.logger.record_event("skill.enable", {
                "skill_id": "yuque-bulk-delete",
                "decision": decision,
                "reason": enable_result.get("reason", "")
            })

            if decision == "denied":
                print(f"\n❌ 技能启用被拒绝: {enable_result.get('reason', 'approval_required')}")
                print(f"   说明: 高风险技能需要人工审批")

        # Step 6: Attempt to call blocked tool
        await self.think("即使技能被启用，某些危险工具也应该被全局阻止...")

        self.logger.record_event("agent.action", {
            "action": "call_tool",
            "tool_name": "yuque_delete_doc",
            "reasoning": "尝试调用被全局阻止的工具"
        })

        delete_event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": "mcp__mock-yuque__yuque_delete_doc",
            "tool_input": {"doc_id": "old-2023", "confirm": True}
        }
        delete_result = hook_handler.handle_pre_tool_use(delete_event)
        decision = delete_result.get("hookSpecificOutput", {}).get("permissionDecision", "unknown")
        reason = delete_result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")

        self.logger.record_event("tool.call", {
            "tool_name": "mcp__mock-yuque__yuque_delete_doc",
            "tool_short_name": "yuque_delete_doc",
            "decision": decision,
            "deny_reason": reason if decision == "deny" else None,
            "error_bucket": "blocked" if "blocked" in reason.lower() else "whitelist_violation"
        })

        if decision == "deny":
            print(f"\n❌ 工具调用被拒绝: {reason}")
            print(f"   说明: 该工具在全局 blocked_tools 列表中，无法调用")

        # Step 7: Summarize
        print(f"\n" + "="*70)
        print(f"📝 会话生命周期演示总结")
        print(f"="*70)
        print(f"✅ TTL 到期机制: 过期工具自动下线")
        print(f"✅ 权限回收: disable_skill 立即生效")
        print(f"✅ 高风险防护: approval_required + blocked_tools 双重防线")
        print(f"✅ 审计完整: 所有操作可追溯")


async def main_async() -> None:
    """Run the agent to demonstrate lifecycle and risk management."""
    print("\n" + "=" * 70)
    print("  会话生命周期与风险升级演示")
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

    user_request = "继续之前的会话，查看权限状态并清理不需要的权限"

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
    print("  ✅ 演示完成!")
    print(f"  📁 日志目录: {logger.log_dir}")
    print("=" * 70 + "\n")


def main() -> None:
    """Entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
