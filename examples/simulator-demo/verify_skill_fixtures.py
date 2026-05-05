#!/usr/bin/env python3
"""
Verify that SkillIndexer can parse the Stage-first skill fixtures.

Stage 2 Task 2.4: Confirms that:
1. SkillIndexer can discover both skill fixtures
2. yuque-doc-edit-staged has correct stage metadata
3. yuque-knowledge-link has no stages (no-stage fallback)
4. Metadata fields are correctly parsed
"""

import sys
from pathlib import Path

# Add project root to path to import SkillIndexer
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from tool_governance.core.skill_indexer import SkillIndexer


def verify_skill_fixtures():
    """Verify that skill fixtures are correctly parsed by SkillIndexer."""
    print("=" * 60)
    print("Skill Fixtures Verification (Stage 2 Task 2.4)")
    print("=" * 60)

    fixtures_dir = Path(__file__).parent / "fixtures" / "skills"
    print(f"\nFixtures directory: {fixtures_dir}")

    if not fixtures_dir.exists():
        print(f"✗ Fixtures directory does not exist: {fixtures_dir}")
        return False

    # Initialize SkillIndexer
    indexer = SkillIndexer(skills_dir=fixtures_dir)

    # Build index
    print("\nBuilding skill index...")
    skill_map = indexer.build_index()

    print(f"✓ Found {len(skill_map)} skills")

    # Verify expected skills exist
    expected_skills = ["yuque-doc-edit-staged", "yuque-knowledge-link"]

    for skill_id in expected_skills:
        if skill_id not in skill_map:
            print(f"✗ Expected skill not found: {skill_id}")
            return False
        print(f"✓ Found skill: {skill_id}")

    # Verify yuque-doc-edit-staged (staged skill)
    print("\n--- Verifying yuque-doc-edit-staged (staged skill) ---")
    staged_meta = skill_map["yuque-doc-edit-staged"]

    # Debug: print full metadata
    print(f"DEBUG: staged_meta = {staged_meta}")
    print(f"DEBUG: staged_meta.stages = {staged_meta.stages}")
    print(f"DEBUG: type(staged_meta.stages) = {type(staged_meta.stages)}")

    if staged_meta.initial_stage != "analysis":
        print(f"✗ Expected initial_stage='analysis', got '{staged_meta.initial_stage}'")
        return False
    print(f"✓ initial_stage: {staged_meta.initial_stage}")

    if not staged_meta.stages:
        print("✗ Expected stages to be defined")
        return False

    expected_stages = ["analysis", "execution", "verification"]
    actual_stages = [s.stage_id for s in staged_meta.stages]

    if actual_stages != expected_stages:
        print(f"✗ Expected stages {expected_stages}, got {actual_stages}")
        return False
    print(f"✓ stages: {actual_stages}")

    # Verify terminal stage
    verification_stage = next(s for s in staged_meta.stages if s.stage_id == "verification")
    if verification_stage.allowed_next_stages != []:
        print(f"✗ Expected 'verification' stage to be terminal (allowed_next_stages=[]), got {verification_stage.allowed_next_stages}")
        return False
    print("✓ 'verification' stage is terminal (allowed_next_stages=[])")

    # Verify yuque-knowledge-link (no-stage skill)
    print("\n--- Verifying yuque-knowledge-link (no-stage skill) ---")
    noStage_meta = skill_map["yuque-knowledge-link"]

    if noStage_meta.stages:
        print(f"✗ Expected no stages, got {len(noStage_meta.stages)} stages")
        return False
    print("✓ No stages defined (no-stage skill)")

    if noStage_meta.initial_stage is not None:
        print(f"✗ Expected initial_stage=None, got '{noStage_meta.initial_stage}'")
        return False
    print("✓ initial_stage: None")

    if not noStage_meta.allowed_tools:
        print("✗ Expected allowed_tools to be defined for no-stage skill")
        return False
    print(f"✓ allowed_tools: {noStage_meta.allowed_tools}")

    # Summary
    print("\n" + "=" * 60)
    print("✓ All skill fixture verifications passed")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = verify_skill_fixtures()
    sys.exit(0 if success else 1)
