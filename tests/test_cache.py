"""Shared cache-contract tests.

The ``formalize-cache-layers`` change places skill metadata and skill
documents on the same :class:`VersionedTTLCache` abstraction.  These
tests verify that the contract — key construction, hit/miss counters,
single-entry invalidation, whole-cache clear — is genuinely
role-agnostic: swapping the stored value type must not change the
observable behaviour.

These tests complement ``test_skill_indexer.py::TestVersionedTTLCache``
(which covers the cache class in isolation) by exercising the
shared-contract invariants that the metadata and doc roles rely on.
"""

from tool_governance.models.skill import SkillContent, SkillMetadata
from tool_governance.utils.cache import VersionedTTLCache


def _meta(skill_id: str = "s1", version: str = "1.0.0") -> SkillMetadata:
    """Construct a minimal SkillMetadata for contract tests."""
    return SkillMetadata(
        skill_id=skill_id,
        name=skill_id,
        description="test",
        allowed_tools=[],
        allowed_ops=[],
        source_path="/tmp/ignored",
        version=version,
    )


class TestSharedCacheContract:
    """Metadata and doc roles share one VersionedTTLCache contract."""

    def test_make_key_is_role_agnostic(self) -> None:
        """Key construction depends on (skill_id, version), not value type.
        Spec: Two-layer caching — key binds to skill_id + version."""
        m = _meta(version="1.2.3")
        assert VersionedTTLCache.make_key("s1", version=m.version) == "s1::1.2.3"

    def test_hit_miss_counters_behave_identically(self) -> None:
        """Both caches maintain hits/misses counters via the same class.
        Spec: cache is a performance layer with observable counters."""
        cache_meta = VersionedTTLCache()
        cache_doc = VersionedTTLCache()
        m = _meta()
        key = VersionedTTLCache.make_key("s1", version=m.version)

        # Miss + put + hit cycle, identical shape on both roles.
        assert cache_meta.get(key) is None
        assert cache_doc.get(key) is None
        cache_meta.put(key, m)
        cache_doc.put(key, SkillContent(metadata=m, sop="body"))
        hit_meta = cache_meta.get(key)
        hit_doc = cache_doc.get(key)
        assert hit_meta is m
        assert isinstance(hit_doc, SkillContent) and hit_doc.sop == "body"
        assert cache_meta.hits == 1 and cache_meta.misses == 1
        assert cache_doc.hits == 1 and cache_doc.misses == 1

    def test_invalidate_is_role_agnostic(self) -> None:
        """Single-entry invalidation empties exactly one key in either role.
        Spec: metadata and document entries honor a common invalidation
        surface (per-entry invalidate)."""
        cache = VersionedTTLCache()
        cache.put("a", _meta("a"))
        cache.put("b", "doc-body")
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == "doc-body"

    def test_clear_empties_regardless_of_value_type(self) -> None:
        """``clear()`` drops all entries regardless of what value type
        was stored.  Spec: whole-cache invalidation surface is uniform."""
        cache_meta = VersionedTTLCache()
        cache_doc = VersionedTTLCache()
        cache_meta.put("k", _meta())
        cache_doc.put("k", SkillContent(metadata=_meta(), sop="body"))
        assert cache_meta.currsize == 1
        assert cache_doc.currsize == 1
        cache_meta.clear()
        cache_doc.clear()
        assert cache_meta.currsize == 0
        assert cache_doc.currsize == 0
