"""Optional Langfuse tracing for governance audit events.

Provides a uniform :class:`LangfuseTracer` interface that the rest of
the system can always call.  When the optional ``langfuse`` dependency
is missing — or installed but not configured via environment variables
— the tracer is a silent no-op so the governance core continues to
function with SQLite-only audit logging.
"""

from __future__ import annotations

import os
from typing import Any

try:  # pragma: no cover — exercised by the absent-package test path
    from langfuse import Langfuse as _LangfuseClient

    _LANGFUSE_IMPORTABLE = True
except Exception:  # noqa: BLE001 — Langfuse import can fail for many reasons
    _LangfuseClient = None
    _LANGFUSE_IMPORTABLE = False


class LangfuseTracer:
    """Map governance events to a Langfuse session trace.

    A single instance caches one Langfuse trace per ``session_id`` and
    appends each audit event as a trace event.  When ``client`` is
    ``None`` every method is a no-op, so call sites never need to
    branch on whether tracing is configured.
    """

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._traces: dict[str, Any] = {}

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def emit(
        self,
        event_type: str,
        session_id: str,
        skill_id: str | None = None,
        tool_name: str | None = None,
        decision: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Record an event on the per-session Langfuse trace.

        Contract:
            Silences:
                - When no client is configured (the library is not
                  installed or the user did not supply credentials)
                  the call is a no-op.
                - Any exception raised by the Langfuse SDK is caught
                  and swallowed — the governance hot path must never
                  fail because tracing is misconfigured.
        """
        if self._client is None:
            return
        try:
            trace = self._traces.get(session_id)
            if trace is None:
                trace = self._client.trace(
                    name="tool-governance",
                    session_id=session_id,
                )
                self._traces[session_id] = trace
            trace.event(
                name=event_type,
                input={
                    "skill_id": skill_id,
                    "tool_name": tool_name,
                    "decision": decision,
                    "detail": detail or {},
                },
            )
        except Exception:  # noqa: BLE001 — see Silences above
            pass


def create_tracer() -> LangfuseTracer:
    """Return a :class:`LangfuseTracer` wired to the environment.

    Returns a no-op tracer when:

    - the ``langfuse`` package is not installed,
    - the ``LANGFUSE_PUBLIC_KEY`` env var is unset (tracing has not
      been opted into), or
    - the Langfuse client constructor raises (misconfiguration must
      not bring down the governance runtime).
    """
    if not _LANGFUSE_IMPORTABLE:
        return LangfuseTracer(client=None)
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return LangfuseTracer(client=None)
    try:
        client = _LangfuseClient()
    except Exception:  # noqa: BLE001 — misconfiguration must not be fatal
        return LangfuseTracer(client=None)
    return LangfuseTracer(client=client)
