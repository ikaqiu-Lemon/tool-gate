"""Tests for the optional Langfuse tracer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tool_governance.core import observability
from tool_governance.core.observability import LangfuseTracer, create_tracer
from tool_governance.storage.sqlite_store import SQLiteStore


class TestLangfuseTracerNoop:
    def test_no_client_emit_is_silent(self) -> None:
        tracer = LangfuseTracer(client=None)
        assert tracer.enabled is False
        tracer.emit("tool.call", "s1", tool_name="Read", decision="allow")

    def test_client_exception_is_swallowed(self) -> None:
        client = MagicMock()
        client.trace.side_effect = RuntimeError("langfuse is down")
        tracer = LangfuseTracer(client=client)
        tracer.emit("skill.read", "s1", skill_id="repo-read")


class TestLangfuseTracerEmit:
    def test_first_event_creates_trace_and_emits_event(self) -> None:
        client = MagicMock()
        trace = MagicMock()
        client.trace.return_value = trace

        tracer = LangfuseTracer(client=client)
        tracer.emit(
            "skill.enable",
            "session-xyz",
            skill_id="repo-read",
            decision="granted",
            detail={"scope": "session"},
        )

        client.trace.assert_called_once_with(
            name="tool-governance", session_id="session-xyz"
        )
        trace.event.assert_called_once()
        kwargs = trace.event.call_args.kwargs
        assert kwargs["name"] == "skill.enable"
        assert kwargs["input"]["skill_id"] == "repo-read"
        assert kwargs["input"]["decision"] == "granted"
        assert kwargs["input"]["detail"] == {"scope": "session"}

    def test_subsequent_events_reuse_trace(self) -> None:
        client = MagicMock()
        client.trace.return_value = MagicMock()
        tracer = LangfuseTracer(client=client)

        tracer.emit("skill.list", "same-session")
        tracer.emit("skill.read", "same-session", skill_id="x")
        tracer.emit("tool.call", "same-session", tool_name="Read", decision="allow")

        assert client.trace.call_count == 1

    def test_distinct_sessions_get_distinct_traces(self) -> None:
        client = MagicMock()
        client.trace.side_effect = [MagicMock(), MagicMock()]
        tracer = LangfuseTracer(client=client)

        tracer.emit("skill.list", "s1")
        tracer.emit("skill.list", "s2")

        assert client.trace.call_count == 2


class TestCreateTracerFactory:
    def test_missing_package_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(observability, "_LANGFUSE_IMPORTABLE", False)
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        tracer = create_tracer()
        assert tracer.enabled is False

    def test_missing_env_var_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(observability, "_LANGFUSE_IMPORTABLE", True)
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        tracer = create_tracer()
        assert tracer.enabled is False

    def test_client_constructor_failure_returns_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(observability, "_LANGFUSE_IMPORTABLE", True)
        monkeypatch.setattr(
            observability,
            "_LangfuseClient",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        tracer = create_tracer()
        assert tracer.enabled is False


class TestSQLiteStoreTracerIntegration:
    def test_append_audit_forwards_to_tracer(self, tmp_path) -> None:
        tracer = MagicMock(spec=LangfuseTracer)
        store = SQLiteStore(tmp_path, tracer=tracer)

        store.append_audit(
            "s1",
            "tool.call",
            tool_name="Read",
            decision="allow",
            detail={"note": "ok"},
        )

        tracer.emit.assert_called_once_with(
            "tool.call",
            "s1",
            skill_id=None,
            tool_name="Read",
            decision="allow",
            detail={"note": "ok"},
        )

    def test_append_audit_works_without_tracer(self, tmp_path) -> None:
        store = SQLiteStore(tmp_path)
        store.append_audit("s1", "tool.call", tool_name="Read", decision="allow")
        rows = store.query_audit(session_id="s1")
        assert len(rows) == 1

    def test_tracer_exception_does_not_fail_audit(self, tmp_path) -> None:
        tracer = MagicMock(spec=LangfuseTracer)
        tracer.emit.side_effect = RuntimeError("tracer broke")
        store = SQLiteStore(tmp_path, tracer=tracer)

        store.append_audit("s1", "tool.call", tool_name="Read", decision="allow")

        rows = store.query_audit(session_id="s1")
        assert len(rows) == 1
