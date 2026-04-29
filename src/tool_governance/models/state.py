"""Session state data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Iterable

from pydantic import BaseModel, Field

from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata


class LoadedSkillInfo(BaseModel):
    """Snapshot of an enabled skill in the session.

    Tracks which stage the skill is in and when it was last invoked.
    Lives inside SessionState.skills_loaded, keyed by skill_id.

    Classification (see openspec change
    ``separate-runtime-and-persisted-state`` stageA_notes.md):
    every field below is **persisted-only** — it carries cross-turn
    continuity that must survive hook process restarts.
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

    Classification (openspec change ``separate-runtime-and-persisted-state``,
    Stage A):
    - **persisted-only**: ``session_id``, ``skills_loaded``,
      ``active_grants``, ``created_at``, ``updated_at``
    - **derived — excluded from the persisted payload**:
      ``active_tools`` (authoritative computation =
      ``RuntimeContext.active_tools`` / ``compute_active_tools``),
      ``skills_metadata`` (authoritative source =
      ``SkillIndexer._metadata_cache``, exposed via
      ``RuntimeContext.all_skills_metadata``).
    - **runtime-only**: none today — all derivations are still
      written back to ``SessionState`` rather than held in an
      ephemeral runtime context.  Stage B introduces ``RuntimeContext``
      to host them off-object.
    """

    # persisted-only: row identity in the ``sessions`` table.
    session_id: str
    # derived (excluded from persisted payload): skill metadata.  Real
    # authority since ``formalize-cache-layers`` lives in
    # ``SkillIndexer._metadata_cache``; this field is a session-level
    # mirror.  Stage D of ``migrate-entrypoints-to-runtime-flow``
    # excluded it from persistence after all MCP / LangChain entry
    # points migrated to reading from ``RuntimeContext.all_skills_metadata``.
    skills_metadata: dict[str, SkillMetadata] = Field(default_factory=dict)
    # persisted-only: which skills the session has enabled, keyed by
    # skill_id.  Each ``LoadedSkillInfo`` carries the current_stage
    # and last_used_at that must survive cross-hook restarts.
    skills_loaded: dict[str, LoadedSkillInfo] = Field(default_factory=dict)
    # derived — excluded from the persisted payload at Stage C3.
    # Authoritative computation lives in ``RuntimeContext.active_tools``
    # (see ``core/runtime_context.py``); this field is kept on the
    # model only so unmigrated readers that still call
    # ``ToolRewriter.recompute_active_tools(state)`` or inspect
    # ``state.active_tools`` in-memory keep working during the same
    # turn.  It is NOT written to disk by ``state_manager.save`` —
    # see ``to_persisted_dict`` below.
    active_tools: list[str] = Field(default_factory=list)
    # persisted-only: skill_id -> Grant for every non-expired,
    # non-revoked grant.  Invariant: at most one active Grant per
    # (session_id, skill_id); re-enabling a skill overwrites the
    # previous entry.  The ``Grant.grant_id`` inside each value is
    # the authoritative identifier for audit records; the dict key
    # is the lookup handle used by enable/disable/run_skill_action.
    active_grants: dict[str, Grant] = Field(default_factory=dict)
    # persisted-only: audit anchor.  Set once on row insert by the
    # pydantic default factory; preserved by ``SQLiteStore.save_session``
    # on upsert.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # persisted-only: audit anchor.  Rewritten on every upsert by
    # ``SQLiteStore.save_session``.
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Fields excluded from the persisted payload.  Stage C3 of
    # ``separate-runtime-and-persisted-state`` excluded ``active_tools``;
    # Stage D of ``migrate-entrypoints-to-runtime-flow`` added
    # ``skills_metadata`` after all MCP / LangChain entry points migrated
    # to reading from ``RuntimeContext.all_skills_metadata`` instead of
    # the persisted mirror.  See the class-level classification docstring.
    DERIVED_FIELDS: ClassVar[frozenset[str]] = frozenset({"active_tools", "skills_metadata"})

    def to_persisted_dict(self, mode: str = "json") -> dict[str, Any]:
        """Dump the persisted subset of this state.

        Stage C3 of ``separate-runtime-and-persisted-state`` narrowed
        the ``state_manager.save`` path to route through this method
        instead of a full ``model_dump_json()``.  Stage D of
        ``migrate-entrypoints-to-runtime-flow`` expanded the exclusion
        set to include ``skills_metadata`` after all entry points
        migrated to reading from ``RuntimeContext.all_skills_metadata``
        (which sources from ``SkillIndexer``) instead of the persisted
        mirror.
        """
        return self.model_dump(mode=mode, exclude=self.DERIVED_FIELDS)

    def sync_from_runtime(self, runtime_active_tools: Iterable[str]) -> None:
        """Mirror the runtime view's ``active_tools`` into the persisted snapshot.

        Compat shim introduced in Stage C of
        ``separate-runtime-and-persisted-state``.  The authoritative
        derivation is ``RuntimeContext.active_tools`` (computed once
        per turn by ``hook_handler``), but some unmigrated readers —
        ``mcp_server`` meta-tools, ``policy_engine.is_tool_allowed``,
        and any functional test that still inspects
        ``state.active_tools`` directly — continue to read the
        in-memory field.  Calling this method after
        ``build_runtime_context`` keeps the two in lockstep without
        duplicating the derivation formula.

        After Stage C3, ``active_tools`` is no longer written to disk
        — only held in-memory via this mirror — so the field's value
        is authoritative only within the same turn.  The method and
        the in-memory field itself can retire once every reader
        consumes ``RuntimeContext.active_tools`` instead.
        """
        self.active_tools = sorted(runtime_active_tools)
