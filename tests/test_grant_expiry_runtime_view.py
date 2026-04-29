"""Grant expiry regression test for runtime-visible tools.

Stage D of ``migrate-entrypoints-to-runtime-flow`` pins the
requirement that expired grants must not contribute tools to
``RuntimeContext.active_tools``.  This test verifies that the
grant-expiry filtering logic in ``build_runtime_context`` correctly
excludes tools from skills whose grants have expired.
"""

import pytest
from datetime import datetime, timedelta

from tool_governance.core.runtime_context import build_runtime_context
from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import LoadedSkillInfo, SessionState


@pytest.fixture()
def repo_read_meta() -> SkillMetadata:
    return SkillMetadata(
        skill_id="repo-read",
        name="RepoRead",
        allowed_tools=["Read", "Glob"],
    )


@pytest.fixture()
def expired_grant() -> Grant:
    """A grant that expired 1 hour ago."""
    return Grant(
        grant_id="grant-expired",
        session_id="test-session",
        skill_id="repo-read",
        allowed_ops=["read"],
        scope="session",
        granted_by="user",
        granted_at=datetime.utcnow() - timedelta(hours=2),
        expires_at=datetime.utcnow() - timedelta(hours=1),
        status="active",
    )


@pytest.fixture()
def active_grant() -> Grant:
    """A grant that expires 1 hour from now."""
    return Grant(
        grant_id="grant-active",
        session_id="test-session",
        skill_id="repo-read",
        allowed_ops=["read"],
        scope="session",
        granted_by="user",
        granted_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        status="active",
    )


class TestGrantExpiryRuntimeView:
    """Pins the requirement that expired grants do not contribute tools
    to the runtime-visible active_tools set.

    Covers spec scenario from ``migrate-entrypoints-to-runtime-flow``:
    "Expired grants excluded from runtime active_tools".
    """

    def test_expired_grant_tools_not_in_runtime_active_tools(
        self, repo_read_meta: SkillMetadata, expired_grant: Grant
    ) -> None:
        """When a skill's grant has expired, its tools must NOT appear
        in ``RuntimeContext.active_tools``.

        This is the core regression guard: even though the skill is in
        ``skills_loaded`` and has metadata, the expired grant means
        the runtime view should exclude its tools.
        """
        state = SessionState(
            session_id="test-session",
            skills_loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            active_grants={"repo-read": expired_grant},
        )
        ctx = build_runtime_context(
            state,
            metadata={"repo-read": repo_read_meta},
        )
        # Meta-tools are always present, but the expired skill's tools
        # should be absent.
        assert "Read" not in ctx.active_tools
        assert "Glob" not in ctx.active_tools
        # Meta-tools still present as baseline.
        assert "mcp__tool-governance__list_skills" in ctx.active_tools

    def test_active_grant_tools_in_runtime_active_tools(
        self, repo_read_meta: SkillMetadata, active_grant: Grant
    ) -> None:
        """When a skill's grant is active and not expired, its tools
        MUST appear in ``RuntimeContext.active_tools``.

        Positive control: verifies that non-expired grants still work.
        """
        state = SessionState(
            session_id="test-session",
            skills_loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            active_grants={"repo-read": active_grant},
        )
        ctx = build_runtime_context(
            state,
            metadata={"repo-read": repo_read_meta},
        )
        assert "Read" in ctx.active_tools
        assert "Glob" in ctx.active_tools

    def test_mixed_expired_and_active_grants(
        self, repo_read_meta: SkillMetadata, expired_grant: Grant, active_grant: Grant
    ) -> None:
        """When multiple skills are loaded, only those with non-expired
        grants should contribute tools to the runtime view.

        Guards against all-or-nothing filtering bugs where one expired
        grant incorrectly affects other skills.
        """
        code_edit_meta = SkillMetadata(
            skill_id="code-edit",
            name="CodeEdit",
            allowed_tools=["Edit", "Write"],
        )
        active_grant_for_code_edit = Grant(
            grant_id="grant-code-edit",
            session_id="test-session",
            skill_id="code-edit",
            allowed_ops=["edit"],
            scope="session",
            granted_by="user",
            granted_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
            status="active",
        )

        state = SessionState(
            session_id="test-session",
            skills_loaded={
                "repo-read": LoadedSkillInfo(skill_id="repo-read"),
                "code-edit": LoadedSkillInfo(skill_id="code-edit"),
            },
            active_grants={
                "repo-read": expired_grant,
                "code-edit": active_grant_for_code_edit,
            },
        )
        ctx = build_runtime_context(
            state,
            metadata={
                "repo-read": repo_read_meta,
                "code-edit": code_edit_meta,
            },
        )
        # Expired skill's tools should be absent.
        assert "Read" not in ctx.active_tools
        assert "Glob" not in ctx.active_tools
        # Active skill's tools should be present.
        assert "Edit" in ctx.active_tools
        assert "Write" in ctx.active_tools

    def test_no_grant_means_no_tools(self, repo_read_meta: SkillMetadata) -> None:
        """A skill in ``skills_loaded`` but with no grant in
        ``active_grants`` should not contribute tools.

        This can happen if the grant was revoked or expired and cleaned
        up from ``active_grants`` but the skill wasn't removed from
        ``skills_loaded`` yet.
        """
        state = SessionState(
            session_id="test-session",
            skills_loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            active_grants={},  # No grant for repo-read
        )
        ctx = build_runtime_context(
            state,
            metadata={"repo-read": repo_read_meta},
        )
        assert "Read" not in ctx.active_tools
        assert "Glob" not in ctx.active_tools
