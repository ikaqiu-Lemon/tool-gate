"""Skill data models — SkillMetadata, StageDefinition, SkillContent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StageDefinition(BaseModel):
    """A named stage within a skill, each exposing a different tool set.

    Skills can define multiple stages (e.g. "plan", "execute", "review")
    to progressively widen or narrow the set of tools available.
    change_stage switches the active stage at runtime.
    """

    stage_id: str
    description: str = ""
    # Tools available when this stage is active.  Overrides the
    # skill-level allowed_tools for the duration of the stage.
    allowed_tools: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    """Metadata parsed from a SKILL.md frontmatter.

    This is the "identity card" of a skill: what it is, what it may
    touch, how risky it is, and where it lives on disk.  Loaded once
    during skill discovery and cached by VersionedTTLCache.
    """

    skill_id: str
    name: str
    description: str = ""
    risk_level: Literal["low", "medium", "high"] = "low"
    # Top-level tool whitelist.  If stages are defined, the active
    # stage's allowed_tools takes precedence.
    allowed_tools: list[str] = Field(default_factory=list)
    # Operation names this skill declares (e.g. "lint", "deploy").
    # An empty list is treated as "skill has no named operations".
    allowed_ops: list[str] = Field(default_factory=list)
    stages: list[StageDefinition] = Field(default_factory=list)
    default_ttl: int = 3600
    # Filesystem path to the SKILL.md file; empty when metadata was
    # constructed programmatically rather than parsed from disk.
    source_path: str = ""
    version: str = "1.0.0"


class SkillContent(BaseModel):
    """Full skill content returned by read_skill.

    Combines parsed metadata with the raw SOP body and optional
    usage examples extracted from the SKILL.md file.
    """

    metadata: SkillMetadata
    # Standard-operating-procedure body (Markdown).
    sop: str = ""
    examples: list[str] = Field(default_factory=list)
