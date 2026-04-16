"""Policy engine — evaluates skill authorization requests.

Central decision-maker for whether a skill may be enabled.  Every
``enable_skill`` call passes through ``PolicyEngine.evaluate()``
before a Grant is created.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from tool_governance.models.policy import GovernancePolicy
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import SessionState


class PolicyDecision(BaseModel):
    """Result of a policy evaluation.

    ``allowed=True`` means the skill can be enabled immediately.
    ``allowed=False`` means additional action is needed — the
    ``decision`` field tells the caller what (provide a reason,
    get approval, or give up).
    """

    allowed: bool
    # "auto" = silently granted; "reason_required" = caller must supply
    # a reason string; "approval_required" = out-of-band approval
    # needed; "denied" = unconditionally blocked.
    decision: Literal["auto", "reason_required", "approval_required", "denied"]
    reason: str | None = None


class PolicyEngine:
    """Evaluates enable_skill requests against governance policy."""

    def __init__(self, policy: GovernancePolicy) -> None:
        self._policy = policy

    def evaluate(
        self,
        skill_id: str,
        skill_meta: SkillMetadata,
        state: SessionState,
        reason: str | None = None,
    ) -> PolicyDecision:
        """Evaluate whether a skill can be enabled.

        Precedence: blocked_list → skill-specific policy → risk-level defaults.

        Contract:
            Silences:
                - If a skill-specific policy exists but none of its
                  flags (``approval_required``, ``require_reason``,
                  ``auto_grant``) are ``True``, **all three checks
                  fall through** and evaluation continues to the
                  risk-level defaults in step 3.  This means a
                  ``SkillPolicy(auto_grant=False, require_reason=False,
                  approval_required=False)`` does NOT deny the skill —
                  it just defers to the global risk thresholds.
                - If ``skill_meta.risk_level`` has a value not present
                  in ``default_risk_thresholds`` (e.g. ``"critical"``),
                  the ``.get()`` returns ``"auto"`` as default — the
                  skill is silently auto-granted.
                - When ``threshold == "reason"`` and a reason IS
                  provided, the returned ``decision`` is ``"auto"``
                  (not ``"reason_required"``).  The original reason
                  string is attached but the decision type doesn't
                  distinguish "granted because reason was given" from
                  "granted automatically".
                - An unrecognised threshold string (not ``"auto"``,
                  ``"reason"``, or ``"approval"``) silently falls
                  through to the ``else`` branch and auto-grants.
        """
        # 1. Global blocked list — unconditional deny.
        if skill_id in self._policy.blocked_tools:
            return PolicyDecision(
                allowed=False,
                decision="denied",
                reason=f"Skill '{skill_id}' is in the blocked list",
            )

        # 2. Skill-specific policy override.
        # NB: if the policy exists but all flags are False, none of
        # these branches match and we fall through to step 3.
        sp = self._policy.skill_policies.get(skill_id)
        if sp is not None:
            if sp.approval_required:
                return PolicyDecision(allowed=False, decision="approval_required")
            if sp.require_reason and not reason:
                return PolicyDecision(allowed=False, decision="reason_required")
            if sp.auto_grant:
                return PolicyDecision(allowed=True, decision="auto")

        # 3. Risk-level default thresholds.
        # Unknown risk levels default to "auto" via .get() fallback.
        threshold = self._policy.default_risk_thresholds.get(
            skill_meta.risk_level, "auto"
        )

        if threshold == "auto":
            return PolicyDecision(allowed=True, decision="auto")
        elif threshold == "reason":
            if reason:
                return PolicyDecision(allowed=True, decision="auto", reason=reason)
            return PolicyDecision(allowed=False, decision="reason_required")
        elif threshold == "approval":
            return PolicyDecision(allowed=False, decision="approval_required")
        else:
            # Unrecognised threshold value — default to auto-grant.
            return PolicyDecision(allowed=True, decision="auto")

    def is_tool_allowed(self, tool_name: str, state: SessionState) -> bool:
        """Check if a tool is in the current active_tools."""
        return tool_name in state.active_tools

    def get_max_ttl(self, skill_id: str) -> int:
        """Return the max TTL for a skill (skill-specific or global default).

        Contract:
            Silences:
                - If no skill-specific policy exists, silently falls
                  back to ``default_ttl`` with no indication that the
                  value is a global default rather than a per-skill
                  setting.
        """
        sp = self._policy.skill_policies.get(skill_id)
        if sp is not None:
            return sp.max_ttl
        return self._policy.default_ttl

    def cap_ttl(self, skill_id: str, requested_ttl: int) -> int:
        """Cap requested TTL to the maximum allowed.

        Returns ``min(requested_ttl, max_ttl)``.  If ``requested_ttl``
        is negative, the negative value passes through uncapped (since
        any negative < max_ttl is False).
        """
        max_ttl = self.get_max_ttl(skill_id)
        return min(requested_ttl, max_ttl)
