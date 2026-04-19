"""Audit-log query helpers for functional tests."""

from __future__ import annotations

import json
from typing import Any


def events_of_type(runtime, session_id: str, event_type: str) -> list[dict[str, Any]]:
    """Thin wrapper over ``SQLiteStore.query_audit`` filtered by type."""
    return runtime.store.query_audit(session_id=session_id, event_type=event_type)


def decoded_detail(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("detail")
    if not raw:
        return {}
    return json.loads(raw)
