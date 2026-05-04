"""Stage D Integration Tests — verify stage governance integrates correctly.

These tests verify that the stage transition enforcement implemented in Stages A-C
correctly integrates with:
- State persistence (SessionState serialization/deserialization)
- Backward compatibility (missing fields get defaults)

Note: Active tools integration and audit integration are already covered by
functional tests (test_functional_stage.py) and unit tests (test_stage_transition_governance.py).
Stage D focuses on persistence and compatibility integration that isn't covered elsewhere.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tool_governance.models.state import LoadedSkillInfo, SessionState, StageTransitionRecord


class TestPersistenceIntegration:
    """D.4-D.6: Verify stage state persists correctly across sessions."""

    def test_stage_state_serializes_to_session_state(self):
        """D.4: Stage lifecycle fields serialize correctly to SessionState."""
        clock = datetime.now(timezone.utc)
        loaded_skill = LoadedSkillInfo(
            skill_id="mock-stageful",
            version="1.0.0",
            current_stage="analysis",
            stage_entered_at=clock,
            stage_history=[],
            exited_stages=[],
        )

        state = SessionState(
            session_id="test-session",
            skills_loaded={"mock-stageful": loaded_skill},
            skills_metadata={},
            active_grants={},
            active_tools=[],
            created_at=clock,
            updated_at=clock,
        )

        serialized = state.model_dump()
        skill_data = serialized["skills_loaded"]["mock-stageful"]
        assert skill_data["current_stage"] == "analysis"
        assert skill_data["stage_entered_at"] is not None
        assert skill_data["stage_history"] == []
        assert skill_data["exited_stages"] == []

    def test_stage_state_deserializes_from_session_state(self):
        """D.5: Stage lifecycle fields deserialize correctly from SessionState."""
        clock = datetime.now(timezone.utc)
        data = {
            "session_id": "test-session",
            "skills_loaded": {
                "mock-stageful": {
                    "skill_id": "mock-stageful",
                    "version": "1.0.0",
                    "current_stage": "execution",
                    "stage_entered_at": clock.isoformat(),
                    "stage_history": [
                        {
                            "from_stage": "analysis",
                            "to_stage": "execution",
                            "transitioned_at": clock.isoformat(),
                        }
                    ],
                    "exited_stages": ["analysis"],
                }
            },
            "skills_metadata": {},
            "active_grants": {},
            "active_tools": [],
            "created_at": clock.isoformat(),
            "updated_at": clock.isoformat(),
        }

        state = SessionState.model_validate(data)
        loaded = state.skills_loaded["mock-stageful"]
        assert loaded.current_stage == "execution"
        assert loaded.stage_entered_at is not None
        assert len(loaded.stage_history) == 1
        assert loaded.stage_history[0].from_stage == "analysis"
        assert loaded.exited_stages == ["analysis"]

    def test_backward_compatibility_missing_stage_fields(self):
        """D.6: SessionState with missing stage fields deserializes with defaults."""
        clock = datetime.now(timezone.utc)
        data = {
            "session_id": "test-session",
            "skills_loaded": {
                "old-skill": {
                    "skill_id": "old-skill",
                    "version": "1.0.0",
                    # Missing: current_stage, stage_entered_at, stage_history, exited_stages
                }
            },
            "skills_metadata": {},
            "active_grants": {},
            "active_tools": [],
            "created_at": clock.isoformat(),
            "updated_at": clock.isoformat(),
        }

        state = SessionState.model_validate(data)
        loaded = state.skills_loaded["old-skill"]
        assert loaded.current_stage is None
        assert loaded.stage_entered_at is None
        assert loaded.stage_history == []
        assert loaded.exited_stages == []

    def test_stage_transition_record_serialization(self):
        """D.7: StageTransitionRecord serializes and deserializes correctly."""
        clock = datetime.now(timezone.utc)
        record = StageTransitionRecord(
            from_stage="analysis",
            to_stage="execution",
            transitioned_at=clock,
        )

        serialized = record.model_dump()
        assert serialized["from_stage"] == "analysis"
        assert serialized["to_stage"] == "execution"
        assert serialized["transitioned_at"] == clock

        # Deserialize
        deserialized = StageTransitionRecord.model_validate(serialized)
        assert deserialized.from_stage == "analysis"
        assert deserialized.to_stage == "execution"
        assert deserialized.transitioned_at == clock

    def test_stage_history_accumulates_transitions(self):
        """D.8: Multiple transitions accumulate in stage_history."""
        clock = datetime.now(timezone.utc)
        loaded_skill = LoadedSkillInfo(
            skill_id="multi-stage",
            version="1.0.0",
            current_stage="stage3",
            stage_entered_at=clock,
            stage_history=[
                StageTransitionRecord(
                    from_stage="stage1",
                    to_stage="stage2",
                    transitioned_at=clock,
                ),
                StageTransitionRecord(
                    from_stage="stage2",
                    to_stage="stage3",
                    transitioned_at=clock,
                ),
            ],
            exited_stages=["stage1", "stage2"],
        )

        state = SessionState(
            session_id="test-session",
            skills_loaded={"multi-stage": loaded_skill},
            skills_metadata={},
            active_grants={},
            active_tools=[],
            created_at=clock,
            updated_at=clock,
        )

        # Serialize and deserialize
        serialized = state.model_dump()
        restored = SessionState.model_validate(serialized)

        loaded = restored.skills_loaded["multi-stage"]
        assert len(loaded.stage_history) == 2
        assert loaded.stage_history[0].from_stage == "stage1"
        assert loaded.stage_history[1].from_stage == "stage2"
        assert loaded.exited_stages == ["stage1", "stage2"]
        assert loaded.current_stage == "stage3"

    def test_empty_stage_history_and_exited_stages(self):
        """D.9: Empty stage_history and exited_stages serialize correctly."""
        clock = datetime.now(timezone.utc)
        loaded_skill = LoadedSkillInfo(
            skill_id="new-skill",
            version="1.0.0",
            current_stage="initial",
            stage_entered_at=clock,
            stage_history=[],
            exited_stages=[],
        )

        state = SessionState(
            session_id="test-session",
            skills_loaded={"new-skill": loaded_skill},
            skills_metadata={},
            active_grants={},
            active_tools=[],
            created_at=clock,
            updated_at=clock,
        )

        serialized = state.model_dump()
        restored = SessionState.model_validate(serialized)

        loaded = restored.skills_loaded["new-skill"]
        assert loaded.stage_history == []
        assert loaded.exited_stages == []
        assert loaded.current_stage == "initial"

    def test_none_stage_fields_for_stageless_skill(self):
        """D.10: Stageless skills have None/empty stage fields that persist correctly."""
        clock = datetime.now(timezone.utc)
        loaded_skill = LoadedSkillInfo(
            skill_id="stageless",
            version="1.0.0",
            current_stage=None,
            stage_entered_at=None,
            stage_history=[],
            exited_stages=[],
        )

        state = SessionState(
            session_id="test-session",
            skills_loaded={"stageless": loaded_skill},
            skills_metadata={},
            active_grants={},
            active_tools=[],
            created_at=clock,
            updated_at=clock,
        )

        serialized = state.model_dump()
        restored = SessionState.model_validate(serialized)

        loaded = restored.skills_loaded["stageless"]
        assert loaded.current_stage is None
        assert loaded.stage_entered_at is None
        assert loaded.stage_history == []
        assert loaded.exited_stages == []
