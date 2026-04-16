"""Grant data model — authorization records."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Grant(BaseModel):
    """A single authorization record created by enable_skill.

    Each Grant ties one skill to one session and tracks which operations
    the skill is permitted to perform, who authorised it, and when
    it expires.  Grants are the runtime "proof of authorisation" that
    run_skill_action checks before executing an operation.
    """

    grant_id: str
    session_id: str
    skill_id: str

    # Empty list means "all ops declared by the skill are allowed".
    allowed_ops: list[str] = Field(default_factory=list)

    # "turn" grants expire at the end of the current LLM turn;
    # "session" grants survive until TTL or explicit revocation.
    scope: Literal["turn", "session"] = "session"

    ttl_seconds: int = 3600

    # Lifecycle: active -> expired (TTL) | revoked (disable_skill).
    status: Literal["active", "expired", "revoked"] = "active"

    # Who authorised this grant: auto (low-risk default), user
    # (explicit approval), or policy (governance-config rule).
    granted_by: Literal["auto", "user", "policy"] = "auto"

    reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
