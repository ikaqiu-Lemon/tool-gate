"""Session state data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata


class LoadedSkillInfo(BaseModel):
    """Snapshot of an enabled skill in the session.

    Tracks which stage the skill is in and when it was last invoked.
    Lives inside SessionState.skills_loaded, keyed by skill_id.
    """

    skill_id: str
    version: str = "1.0.0"
    # Active stage_id, or None if the skill has no stages / is using
    # its top-level allowed_tools.
    current_stage: str | None = None
    last_used_at: datetime | None = None


class SessionState(BaseModel):
    """Full governance state for a single session.

    Central object that the governance engine reads and mutates.
    It tracks *which* skills are known (metadata), *which* are
    currently enabled (loaded), *what* tools are available
    (active_tools), and *what* authorisations exist (grants).
    """

    session_id: str
    # skill_id -> metadata for every discovered skill (enabled or not).
    skills_metadata: dict[str, SkillMetadata] = Field(default_factory=dict)
    # skill_id -> info for currently-enabled skills only.
    skills_loaded: dict[str, LoadedSkillInfo] = Field(default_factory=dict)
    # Union of tools permitted by all active grants; recomputed on
    # enable/disable/stage-change.
    active_tools: list[str] = Field(default_factory=list)
    # grant_id -> Grant for every non-expired, non-revoked grant.
    active_grants: dict[str, Grant] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
