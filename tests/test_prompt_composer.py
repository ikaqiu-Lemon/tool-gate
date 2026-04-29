"""Tests for PromptComposer.

Verifies the text blobs injected into the model's context: skill
catalog formatting, active-tools summary, truncation budget, and
correct handling of enabled vs disabled skills.
"""

import pytest

from tool_governance.core.prompt_composer import PromptComposer
from tool_governance.core.runtime_context import build_runtime_context
from tool_governance.core.tool_rewriter import META_TOOLS
from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import LoadedSkillInfo, SessionState


@pytest.fixture()
def composer() -> PromptComposer:
    return PromptComposer()


class TestComposeContext:
    def test_empty_state(self, composer: PromptComposer) -> None:
        """No skills registered → the context must say so explicitly,
        so the model knows it needs to wait for skills to appear."""
        state = SessionState(session_id="test")
        ctx = composer.compose_context(state)
        assert "No skills registered" in ctx

    def test_with_skills(self, composer: PromptComposer) -> None:
        """A disabled skill should appear with its name and risk level
        so the model can decide whether to enable it."""
        state = SessionState(
            session_id="test",
            skills_metadata={
                "repo-read": SkillMetadata(
                    skill_id="repo-read", name="Repo Read",
                    description="Read code", risk_level="low",
                    allowed_tools=["Read", "Glob"],
                ),
            },
        )
        ctx = composer.compose_context(state)
        assert "Repo Read" in ctx
        assert "low" in ctx

    def test_enabled_skill_shows_detail(self, composer: PromptComposer) -> None:
        """An enabled skill must show [ENABLED] and its tool names.
        The active_tools list is pre-populated with META_TOOLS + skill
        tools to mimic what ToolRewriter.recompute would produce."""
        state = SessionState(
            session_id="test",
            skills_metadata={
                "repo-read": SkillMetadata(
                    skill_id="repo-read", name="Repo Read",
                    allowed_tools=["Read", "Glob"],
                ),
            },
            skills_loaded={
                "repo-read": LoadedSkillInfo(skill_id="repo-read"),
            },
            active_tools=sorted(list(META_TOOLS) + ["Read", "Glob"]),
        )
        ctx = composer.compose_context(state)
        assert "ENABLED" in ctx
        assert "Read" in ctx

    def test_context_length_budget(self, composer: PromptComposer) -> None:
        """20 skills with 60-char descriptions exceed the 800-char
        budget.  Verifies that compose_context hard-truncates to
        stay within _MAX_CONTEXT_LEN."""
        skills = {}
        for i in range(20):
            sid = f"skill-{i}"
            skills[sid] = SkillMetadata(
                skill_id=sid, name=f"Skill {i}",
                description="A" * 60, risk_level="low",
            )
        state = SessionState(session_id="test", skills_metadata=skills)
        ctx = composer.compose_context(state)
        assert len(ctx) <= 800


class TestCatalog:
    def test_no_skills(self, composer: PromptComposer) -> None:
        state = SessionState(session_id="test")
        cat = composer.compose_skill_catalog(state)
        assert "No skills" in cat


class TestActiveToolsPrompt:
    def test_no_active(self, composer: PromptComposer) -> None:
        """When only meta-tools are active (all filtered out), the
        prompt should show the guidance message telling the model
        to use list_skills → read_skill → enable_skill."""
        state = SessionState(session_id="test", active_tools=list(META_TOOLS))
        prompt = composer.compose_active_tools_prompt(state)
        assert "list_skills" in prompt

    def test_with_active(self, composer: PromptComposer) -> None:
        """Non-meta tools must appear in the "Active tools:" line."""
        state = SessionState(
            session_id="test",
            active_tools=sorted(list(META_TOOLS) + ["Read", "Glob"]),
        )
        prompt = composer.compose_active_tools_prompt(state)
        assert "Read" in prompt
        assert "Glob" in prompt


class TestComposeFromRuntimeContext:
    """Stage C of ``separate-runtime-and-persisted-state``.

    The hook layer now builds a ``RuntimeContext`` once per turn and
    passes it to the composer.  These tests pin the new input shape
    and verify that the rendered output derives from the runtime
    view, not from any persisted ``active_tools`` field.
    """

    def test_compose_accepts_runtime_context(
        self, composer: PromptComposer
    ) -> None:
        """Covers tool-surface-control spec:
        "Prompt and tool rewrite consume runtime state, not persisted
        snapshot" — compose_context accepts a RuntimeContext directly.
        """
        meta = SkillMetadata(
            skill_id="repo-read", name="Repo Read", allowed_tools=["Read", "Glob"]
        )
        # Stage D: skills need both skills_loaded entry AND active grant.
        grant = Grant(
            grant_id="g1", session_id="test", skill_id="repo-read", allowed_ops=[]
        )
        state = SessionState(
            session_id="test",
            skills_metadata={"repo-read": meta},
            skills_loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            active_grants={"repo-read": grant},
        )
        ctx = build_runtime_context(state)
        rendered = composer.compose_context(ctx)
        assert "Repo Read" in rendered
        assert "ENABLED" in rendered
        assert "Read" in rendered and "Glob" in rendered

    def test_compose_ignores_stale_state_active_tools_when_ctx_passed(
        self, composer: PromptComposer
    ) -> None:
        """Covers tool-surface-control spec:
        "Prompt composition ignores stale prior-turn derivations" —
        when a RuntimeContext is supplied, the composer must NOT look
        back at ``state.active_tools``; a stale value there must not
        influence the output.
        """
        meta = SkillMetadata(
            skill_id="repo-read", name="Repo Read", allowed_tools=["Read", "Glob"]
        )
        # Stage D: skills need both skills_loaded entry AND active grant.
        grant = Grant(
            grant_id="g1", session_id="test", skill_id="repo-read", allowed_ops=[]
        )
        # Stale legacy field: claims "Edit" is active, but the real
        # state has no loaded skill that grants it.
        state = SessionState(
            session_id="test",
            skills_metadata={"repo-read": meta},
            skills_loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            active_grants={"repo-read": grant},
            active_tools=["Edit"],
        )
        ctx = build_runtime_context(state)
        rendered = composer.compose_active_tools_prompt(ctx)
        # Runtime view is authoritative → "Edit" is NOT present.
        assert "Edit" not in rendered
        assert "Read" in rendered and "Glob" in rendered

    def test_compose_handles_unknown_skill_in_persisted_state(
        self, composer: PromptComposer
    ) -> None:
        """Covers session-lifecycle spec:
        "System degrades safely when persisted state is missing,
        stale, or incomplete" — a persisted skill that no longer
        resolves in the metadata map is silently dropped from the
        catalog rendered out of the RuntimeContext.
        """
        state = SessionState(
            session_id="test",
            # ``ghost`` is loaded but has no matching metadata entry.
            skills_loaded={"ghost": LoadedSkillInfo(skill_id="ghost")},
            skills_metadata={},
        )
        ctx = build_runtime_context(state)
        rendered = composer.compose_skill_catalog(ctx)
        assert "No skills registered" in rendered
        assert "ghost" not in rendered
