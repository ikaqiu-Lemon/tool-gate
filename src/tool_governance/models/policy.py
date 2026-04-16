"""Policy data models for governance configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillPolicy(BaseModel):
    """Per-skill policy override.

    When present in GovernancePolicy.skill_policies, these values
    override the global defaults for the matching skill_id.
    """

    skill_id: str
    # If True, enable_skill grants access without user confirmation.
    auto_grant: bool = True
    # If True, the caller must supply a non-empty reason string.
    require_reason: bool = False
    # Upper bound (seconds) for the TTL the caller may request.
    max_ttl: int = 7200
    # If True, an out-of-band user approval step is required before
    # the grant becomes active (not yet enforced at runtime).
    approval_required: bool = False


class GovernancePolicy(BaseModel):
    """Global governance policy loaded from YAML config.

    Controls how grants are issued: which risk levels get automatic
    grants, what TTL and scope apply by default, and which tools
    are unconditionally blocked regardless of skill permissions.
    """

    # Maps risk level -> grant mode.
    #   "auto"     – grant silently
    #   "reason"   – grant only if a reason string is provided
    #   "approval" – require explicit user approval
    default_risk_thresholds: dict[str, str] = Field(
        default_factory=lambda: {
            "low": "auto",
            "medium": "reason",
            "high": "approval",
        }
    )
    default_ttl: int = 3600
    default_scope: str = "session"
    skill_policies: dict[str, SkillPolicy] = Field(default_factory=dict)
    # Tools listed here are denied even when a skill's allowed_tools
    # includes them — acts as a global deny-list.
    blocked_tools: list[str] = Field(default_factory=list)
