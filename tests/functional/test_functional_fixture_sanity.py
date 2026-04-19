"""Fixture-sanity test (Stage E closeout for verify Issue C1).

Asserts that building the index over ``tests/fixtures/skills/`` returns
exactly the valid ``mock_*`` fixtures and silently skips the intentionally
broken ones (``mock_malformed`` — invalid YAML; ``mock_oversized`` —
file > 100 KB). Exercises the two silent-skip contracts in
``SkillIndexer._index_one`` without depending on any runtime or hook
plumbing.
"""

from __future__ import annotations

from tool_governance.core.skill_indexer import SkillIndexer
from tool_governance.utils.cache import VersionedTTLCache

from ._support.runtime import fixtures_skills_dir


class TestFixtureIndexerSkipsInvalid:
    def test_valid_mocks_indexed_invalid_skipped(self) -> None:
        indexer = SkillIndexer(fixtures_skills_dir(), VersionedTTLCache())
        index = indexer.build_index()
        ids = set(index.keys())

        for expected in (
            "mock_readonly",
            "mock_stageful",
            "mock_sensitive",
            "mock_ttl",
            "mock_refreshable",
        ):
            assert expected in ids, f"missing valid fixture: {expected}"

        # Broken siblings must be silently dropped by the indexer.
        assert "mock_malformed" not in ids
        assert "mock_oversized" not in ids

        # Every indexed id must use the mock_ prefix — the fixture root is
        # isolated from any shipped/production skill tree.
        assert all(sid.startswith("mock_") for sid in ids)
