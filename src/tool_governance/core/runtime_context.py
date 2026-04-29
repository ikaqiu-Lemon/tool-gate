"""Per-turn runtime view — boundary between persisted state and derivations.

``RuntimeContext`` is the Stage B artifact of the
``separate-runtime-and-persisted-state`` change: a frozen, read-only
snapshot that a turn computes once from ``(persisted SessionState,
current metadata, current policy, current clock)`` and then hands to
any code that today reads derived fields off ``SessionState`` directly
(``state.active_tools``, ``state.skills_metadata``).

The builder is a pure function: it does not mutate the input
``SessionState``, does not write to SQLite, and does not call the
indexer's rebuild path.  It is safe to invoke more than once per turn.

Stage B wires this boundary into the two read-heavy hook entries
(``handle_pre_tool_use`` / ``handle_post_tool_use``) while Stage C
will migrate the remaining callers (``tool_rewriter`` / ``prompt_composer``
/ ``mcp_server``).  Until that migration, callers that still pass a
``SessionState`` keep working unchanged — ``RuntimeContext`` is
additive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from tool_governance.core.tool_rewriter import META_TOOLS, ToolRewriter
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import LoadedSkillInfo, SessionState


@dataclass(frozen=True)
class EnabledSkillView:
    """A (skill_id, metadata, loaded_info) triple for one enabled skill.

    Resolved at ``build_runtime_context`` time.  Skills referenced by
    ``state.skills_loaded`` but absent from the metadata map are
    silently dropped — this is the "System degrades safely" path in
    ``session-lifecycle`` spec.
    """

    skill_id: str
    metadata: SkillMetadata
    loaded_info: LoadedSkillInfo


@dataclass(frozen=True)
class PolicySnapshot:
    """Policy inputs the turn was evaluated under.

    Frozen so a held reference can be compared later without worry
    about mutation.  Only the ``blocked_tools`` set matters for
    rewrite today; additional policy knobs can join as Stage C adds
    them without breaking callers.
    """

    blocked_tools: frozenset[str]


@dataclass(frozen=True)
class RuntimeContext:
    """Per-turn runtime view derived from the persisted SessionState.

    All fields are computed, not loaded.  ``RuntimeContext`` is never
    persisted and must not be stored in ``SessionState``.

    Attributes:
        active_tools: Sorted tuple of tool names visible to the model
            this turn, equal to ``meta_tools ∪ ⋃ stage_tools(enabled)
            − blocked_tools``.
        enabled_skills: One ``EnabledSkillView`` per skill that is
            both present in ``state.skills_loaded`` AND resolvable via
            the metadata map.
        all_skills_metadata: The metadata map used to build this view.
            Kept on the context so gate-time classification can inspect
            non-enabled skills without a second lookup.
        policy: The policy inputs the view was derived under.
        clock: The build timestamp.  Present so tests can pin the
            derivation and future Stage C callers can log it.
    """

    active_tools: tuple[str, ...]
    enabled_skills: tuple[EnabledSkillView, ...]
    all_skills_metadata: Mapping[str, SkillMetadata]
    policy: PolicySnapshot
    clock: datetime

    def enabled_skill_ids(self) -> frozenset[str]:
        return frozenset(sv.skill_id for sv in self.enabled_skills)

    def active_tools_set(self) -> frozenset[str]:
        return frozenset(self.active_tools)


def build_runtime_context(
    state: SessionState,
    metadata: Mapping[str, SkillMetadata] | None = None,
    blocked_tools: Iterable[str] = (),
    clock: datetime | None = None,
) -> RuntimeContext:
    """Derive a ``RuntimeContext`` from persisted state + current context.

    Pure function.  Does not mutate ``state``.  Does not hit SQLite.
    Does not trigger an indexer rebuild — callers decide whether to
    pass ``indexer.current_index()`` (authoritative, post
    ``formalize-cache-layers``) or ``state.skills_metadata`` (legacy
    snapshot).

    Args:
        state: The loaded SessionState.  Read only.
        metadata: The authoritative skill metadata map.  If ``None``
            or empty, the function falls back to ``state.skills_metadata``
            for backward compatibility during Stage B.  Stage C will
            drop the fallback once every caller passes the indexer.
        blocked_tools: Tools to strip from the final set.  Usually
            ``tool_rewriter.blocked_tools``.
        clock: Timestamp for the context.  Defaults to ``datetime.utcnow``
            so tests that want determinism can inject their own.

    Returns:
        A frozen ``RuntimeContext``.  The ``active_tools`` tuple is
        sorted for deterministic equality; ``enabled_skills`` reflects
        the iteration order of ``state.skills_loaded``.
    """
    resolved_clock = clock if clock is not None else datetime.utcnow()
    blocked = frozenset(blocked_tools)
    effective_metadata: Mapping[str, SkillMetadata] = (
        metadata if metadata else state.skills_metadata
    )

    enabled: list[EnabledSkillView] = []
    tools: set[str] = set(META_TOOLS)
    for skill_id, loaded in state.skills_loaded.items():
        meta = effective_metadata.get(skill_id)
        if meta is None:
            # Safe degradation: unknown skill contributes zero tools.
            continue

        # Stage D of ``migrate-entrypoints-to-runtime-flow``: filter
        # out skills whose grants have expired.  A skill in
        # ``skills_loaded`` but with no grant or an expired grant
        # contributes zero tools to the runtime view.
        grant = state.active_grants.get(skill_id)
        if grant is None:
            # No grant means no authorization — skip this skill.
            continue
        if grant.expires_at and grant.expires_at < resolved_clock:
            # Grant has expired — skip this skill.
            continue

        enabled.append(
            EnabledSkillView(skill_id=skill_id, metadata=meta, loaded_info=loaded)
        )
        tools.update(ToolRewriter.get_stage_tools(meta, loaded.current_stage))
    tools -= blocked

    return RuntimeContext(
        active_tools=tuple(sorted(tools)),
        enabled_skills=tuple(enabled),
        all_skills_metadata=effective_metadata,
        policy=PolicySnapshot(blocked_tools=blocked),
        clock=resolved_clock,
    )
