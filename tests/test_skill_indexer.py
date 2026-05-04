"""Tests for SkillIndexer — scanning, parsing, caching, edge cases.

Covers the full indexing pipeline: frontmatter parsing, directory
scanning with skip/error handling, metadata field extraction,
stage parsing, read_skill caching, and the VersionedTTLCache it
depends on.
"""

from pathlib import Path

import pytest

from tool_governance.core.skill_indexer import SkillIndexer, _parse_frontmatter
from tool_governance.utils.cache import VersionedTTLCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with two sample SKILL.md files.

    - ``repo-read``: simple skill (no stages, low risk, 3 tools, 2 ops)
    - ``code-edit``: staged skill (2 stages with different tool sets)

    The YAML is hand-written to exercise the full frontmatter parser:
    lists, nested dicts, quoted strings.
    """
    # repo-read: simple, stage-less skill
    repo_read = tmp_path / "repo-read"
    repo_read.mkdir()
    (repo_read / "SKILL.md").write_text(
        '---\n'
        'name: Repo Read\n'
        'description: "Read-only code exploration."\n'
        'risk_level: low\n'
        'version: "1.0.0"\n'
        'allowed_tools:\n'
        '  - Read\n'
        '  - Glob\n'
        '  - Grep\n'
        'allowed_ops:\n'
        '  - search\n'
        '  - read_file\n'
        '---\n\n'
        '# Repo Read\n\n'
        'Read-only exploration.\n',
        encoding="utf-8",
    )

    # code-edit: staged skill (analysis → execution)
    code_edit = tmp_path / "code-edit"
    code_edit.mkdir()
    (code_edit / "SKILL.md").write_text(
        '---\n'
        'name: Code Edit\n'
        'description: "Staged code editing."\n'
        'risk_level: medium\n'
        'version: "1.0.0"\n'
        'stages:\n'
        '  - stage_id: analysis\n'
        '    description: Read-only analysis\n'
        '    allowed_tools:\n'
        '      - Read\n'
        '      - Glob\n'
        '  - stage_id: execution\n'
        '    description: Write phase\n'
        '    allowed_tools:\n'
        '      - Edit\n'
        '      - Write\n'
        'allowed_ops:\n'
        '  - analyze\n'
        '  - edit\n'
        '---\n\n'
        '# Code Edit\n\n'
        'Staged workflow.\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def indexer(skills_dir: Path) -> SkillIndexer:
    return SkillIndexer(skills_dir)


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    """Unit tests for the low-level frontmatter splitter."""

    def test_valid_frontmatter(self) -> None:
        """Well-formed frontmatter must yield a dict and a body
        with the YAML block stripped."""
        text = '---\nname: Test\nrisk_level: low\n---\n\n# Body\n'
        fm, body = _parse_frontmatter(text)
        assert fm["name"] == "Test"
        assert "# Body" in body

    def test_no_frontmatter(self) -> None:
        """Files without opening ``---`` must return ({}, full_text)
        so the caller knows no metadata was found."""
        text = "# Just a heading\n\nNo frontmatter here."
        fm, body = _parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_invalid_yaml(self) -> None:
        """Syntactically invalid YAML between delimiters must raise
        (not silently return {}) — the caller decides how to handle."""
        text = "---\n: invalid: yaml: [unclosed\n---\n\nbody"
        with pytest.raises(Exception):
            _parse_frontmatter(text)


# ---------------------------------------------------------------------------
# SkillIndexer.build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    """Tests for directory scanning and metadata extraction."""

    def test_scans_all_skills(self, indexer: SkillIndexer) -> None:
        """Both subdirectories with valid SKILL.md files must appear
        in the index."""
        index = indexer.build_index()
        assert "repo-read" in index
        assert "code-edit" in index
        assert len(index) == 2

    def test_metadata_fields(self, indexer: SkillIndexer) -> None:
        """Verify that all frontmatter fields are correctly extracted
        into the SkillMetadata object — name, risk, tools, ops."""
        index = indexer.build_index()
        meta = index["repo-read"]
        assert meta.name == "Repo Read"
        assert meta.risk_level == "low"
        assert meta.allowed_tools == ["Read", "Glob", "Grep"]
        assert meta.allowed_ops == ["search", "read_file"]

    def test_stages_parsed(self, indexer: SkillIndexer) -> None:
        """Nested stage definitions must survive parsing with correct
        ordering, IDs, and per-stage tool lists."""
        index = indexer.build_index()
        meta = index["code-edit"]
        assert len(meta.stages) == 2
        assert meta.stages[0].stage_id == "analysis"
        assert meta.stages[0].allowed_tools == ["Read", "Glob"]
        assert meta.stages[1].stage_id == "execution"
        assert meta.stages[1].allowed_tools == ["Edit", "Write"]

    def test_empty_directory(self, tmp_path: Path) -> None:
        """An empty skills directory must produce an empty index,
        not an error."""
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert index == {}

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """A nonexistent skills directory must produce an empty index
        (logged warning, not an exception)."""
        indexer = SkillIndexer(tmp_path / "nonexistent")
        index = indexer.build_index()
        assert index == {}

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        """A skill with invalid YAML must be silently skipped while
        other valid skills are still indexed — guards the broad
        except-Exception catch in build_index."""
        bad = tmp_path / "bad-skill"
        bad.mkdir()
        (bad / "SKILL.md").write_text(
            "---\n: [invalid yaml\n---\n\nbody",
            encoding="utf-8",
        )
        good = tmp_path / "good-skill"
        good.mkdir()
        (good / "SKILL.md").write_text(
            '---\nname: Good\ndescription: "Works."\n---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert "good-skill" in index
        assert "bad-skill" not in index

    def test_oversized_file_skipped(self, tmp_path: Path) -> None:
        """A SKILL.md exceeding MAX_FILE_SIZE (100 KB) must be
        skipped — guards the size limit in _index_one."""
        big = tmp_path / "big-skill"
        big.mkdir()
        (big / "SKILL.md").write_text(
            '---\nname: Big\n---\n\n' + "x" * (100 * 1024 + 1),
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert "big-skill" not in index

    def test_description_truncated(self, tmp_path: Path) -> None:
        """A 600-char description must be truncated to
        MAX_DESCRIPTION_LEN (500) — guards the truncation in
        _build_metadata."""
        d = tmp_path / "long-desc"
        d.mkdir()
        long_desc = "A" * 600
        (d / "SKILL.md").write_text(
            f'---\nname: Long\ndescription: "{long_desc}"\n---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert len(index["long-desc"].description) == 500

    def test_no_frontmatter_skipped(self, tmp_path: Path) -> None:
        """A SKILL.md with no ``---`` delimiters must be skipped
        (empty frontmatter dict → logged warning)."""
        d = tmp_path / "no-fm"
        d.mkdir()
        (d / "SKILL.md").write_text("# Just markdown\n\nNo frontmatter.", encoding="utf-8")
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert "no-fm" not in index

    def test_parse_initial_stage(self, tmp_path: Path) -> None:
        """Verify initial_stage is parsed from frontmatter."""
        d = tmp_path / "staged-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Staged Skill\n'
            'initial_stage: diagnosis\n'
            'stages:\n'
            '  - stage_id: diagnosis\n'
            '    allowed_tools: [Read]\n'
            '  - stage_id: execution\n'
            '    allowed_tools: [Write]\n'
            '---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        assert index["staged-skill"].initial_stage == "diagnosis"

    def test_parse_allowed_next_stages(self, tmp_path: Path) -> None:
        """Verify allowed_next_stages is parsed from stage definitions."""
        d = tmp_path / "workflow-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Workflow Skill\n'
            'stages:\n'
            '  - stage_id: analysis\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: [execution, abort]\n'
            '  - stage_id: execution\n'
            '    allowed_tools: [Write]\n'
            '    allowed_next_stages: [verify]\n'
            '  - stage_id: verify\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: []\n'
            '  - stage_id: abort\n'
            '    allowed_tools: []\n'
            '    allowed_next_stages: []\n'
            '---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        meta = index["workflow-skill"]
        assert meta.stages[0].allowed_next_stages == ["execution", "abort"]
        assert meta.stages[1].allowed_next_stages == ["verify"]
        assert meta.stages[2].allowed_next_stages == []
        assert meta.stages[3].allowed_next_stages == []

    def test_terminal_stage_preserved(self, tmp_path: Path) -> None:
        """Verify allowed_next_stages: [] is preserved as empty list (terminal stage)."""
        d = tmp_path / "terminal-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Terminal Skill\n'
            'stages:\n'
            '  - stage_id: complete\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: []\n'
            '---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        stage = index["terminal-skill"].stages[0]
        assert stage.allowed_next_stages == []
        assert stage.allowed_next_stages is not None

    def test_skill_without_stages_remains_valid(self, tmp_path: Path) -> None:
        """Verify skills without stages field remain valid."""
        d = tmp_path / "simple-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Simple Skill\n'
            'allowed_tools: [Read, Write]\n'
            '---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        meta = index["simple-skill"]
        assert meta.stages == []
        assert meta.allowed_tools == ["Read", "Write"]
        assert meta.initial_stage is None

    def test_skill_with_stages_but_no_initial_stage(self, tmp_path: Path) -> None:
        """Verify skills with stages but no initial_stage are valid."""
        d = tmp_path / "no-initial"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: No Initial\n'
            'stages:\n'
            '  - stage_id: first\n'
            '    allowed_tools: [Read]\n'
            '  - stage_id: second\n'
            '    allowed_tools: [Write]\n'
            '---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        index = indexer.build_index()
        meta = index["no-initial"]
        assert len(meta.stages) == 2
        assert meta.initial_stage is None


# ---------------------------------------------------------------------------
# SkillIndexer.list_skills / read_skill / refresh
# ---------------------------------------------------------------------------

class TestListAndRead:
    def test_list_skills(self, indexer: SkillIndexer) -> None:
        """list_skills must return metadata for all indexed skills
        (lazy-builds the index on first call)."""
        skills = indexer.list_skills()
        ids = {s.skill_id for s in skills}
        assert "repo-read" in ids
        assert "code-edit" in ids

    def test_read_skill_returns_content(self, indexer: SkillIndexer) -> None:
        """read_skill must return the metadata plus the SOP body
        (markdown after the frontmatter)."""
        indexer.build_index()
        content = indexer.read_skill("repo-read")
        assert content is not None
        assert content.metadata.skill_id == "repo-read"
        assert "Read-only exploration" in content.sop

    def test_read_skill_nonexistent(self, indexer: SkillIndexer) -> None:
        """An unknown skill_id must return None, not raise."""
        indexer.build_index()
        assert indexer.read_skill("nonexistent") is None

    def test_read_skill_cache_hit(self, indexer: SkillIndexer) -> None:
        """Second read of the same skill must return the exact same
        object (identity check) — proves the TTL cache is hit."""
        indexer.build_index()
        content1 = indexer.read_skill("repo-read")
        content2 = indexer.read_skill("repo-read")
        assert content1 is content2  # same object from cache

    def test_refresh_clears_and_rebuilds(self, skills_dir: Path) -> None:
        """After adding a new skill directory and calling refresh(),
        the new skill must appear in the index — proves that caches
        are cleared and the directory is re-scanned."""
        indexer = SkillIndexer(skills_dir)
        indexer.build_index()
        assert len(indexer.list_skills()) == 2

        # Add a new skill after initial indexing.
        new_skill = skills_dir / "new-skill"
        new_skill.mkdir()
        (new_skill / "SKILL.md").write_text(
            '---\nname: New\ndescription: "Fresh."\n---\n\nbody',
            encoding="utf-8",
        )

        count = indexer.refresh()
        assert count == 3
        assert any(s.skill_id == "new-skill" for s in indexer.list_skills())

    def test_read_skill_exposes_initial_stage(self, tmp_path: Path) -> None:
        """read_skill must expose initial_stage in metadata."""
        d = tmp_path / "staged-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Staged Skill\n'
            'initial_stage: diagnosis\n'
            'stages:\n'
            '  - stage_id: diagnosis\n'
            '    allowed_tools: [Read]\n'
            '  - stage_id: execution\n'
            '    allowed_tools: [Write]\n'
            '---\n\nSOP body',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        indexer.build_index()
        content = indexer.read_skill("staged-skill")
        assert content is not None
        assert content.metadata.initial_stage == "diagnosis"
        assert content.sop == "SOP body"

    def test_read_skill_exposes_allowed_next_stages(self, tmp_path: Path) -> None:
        """read_skill must expose allowed_next_stages for each stage."""
        d = tmp_path / "workflow-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Workflow Skill\n'
            'stages:\n'
            '  - stage_id: analysis\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: [execution, abort]\n'
            '  - stage_id: execution\n'
            '    allowed_tools: [Write]\n'
            '    allowed_next_stages: [verify]\n'
            '  - stage_id: verify\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: []\n'
            '  - stage_id: abort\n'
            '    allowed_tools: []\n'
            '    allowed_next_stages: []\n'
            '---\n\nWorkflow SOP',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        indexer.build_index()
        content = indexer.read_skill("workflow-skill")
        assert content is not None
        assert len(content.metadata.stages) == 4
        assert content.metadata.stages[0].allowed_next_stages == ["execution", "abort"]
        assert content.metadata.stages[1].allowed_next_stages == ["verify"]
        assert content.metadata.stages[2].allowed_next_stages == []
        assert content.metadata.stages[3].allowed_next_stages == []

    def test_read_skill_terminal_stage_preserved(self, tmp_path: Path) -> None:
        """read_skill must preserve empty list for terminal stages."""
        d = tmp_path / "terminal-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Terminal Skill\n'
            'stages:\n'
            '  - stage_id: final\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: []\n'
            '---\n\nFinal stage',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        indexer.build_index()
        content = indexer.read_skill("terminal-skill")
        assert content is not None
        assert content.metadata.stages[0].allowed_next_stages == []
        # Verify it's an empty list, not None
        assert isinstance(content.metadata.stages[0].allowed_next_stages, list)

    def test_read_skill_non_staged_skill_exposes_allowed_tools(self, tmp_path: Path) -> None:
        """read_skill on non-staged skill must expose skill-level allowed_tools."""
        d = tmp_path / "simple-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Simple Skill\n'
            'allowed_tools: [Read, Write]\n'
            '---\n\nSimple SOP',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        indexer.build_index()
        content = indexer.read_skill("simple-skill")
        assert content is not None
        assert content.metadata.allowed_tools == ["Read", "Write"]
        assert content.metadata.stages == []
        assert content.metadata.initial_stage is None

    def test_read_skill_serialization_includes_new_fields(self, tmp_path: Path) -> None:
        """Verify model_dump() includes initial_stage and allowed_next_stages."""
        d = tmp_path / "full-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\n'
            'name: Full Skill\n'
            'initial_stage: start\n'
            'stages:\n'
            '  - stage_id: start\n'
            '    allowed_tools: [Read]\n'
            '    allowed_next_stages: [end]\n'
            '  - stage_id: end\n'
            '    allowed_tools: [Write]\n'
            '    allowed_next_stages: []\n'
            '---\n\nFull workflow',
            encoding="utf-8",
        )
        indexer = SkillIndexer(tmp_path)
        indexer.build_index()
        content = indexer.read_skill("full-skill")
        assert content is not None

        # Serialize to dict (same as MCP server does)
        data = content.model_dump()

        # Verify new fields are present in serialized output
        assert "initial_stage" in data["metadata"]
        assert data["metadata"]["initial_stage"] == "start"
        assert len(data["metadata"]["stages"]) == 2
        assert "allowed_next_stages" in data["metadata"]["stages"][0]
        assert data["metadata"]["stages"][0]["allowed_next_stages"] == ["end"]
        assert data["metadata"]["stages"][1]["allowed_next_stages"] == []


# ---------------------------------------------------------------------------
# VersionedTTLCache
# ---------------------------------------------------------------------------

class TestVersionedTTLCache:
    """Unit tests for the cache used by SkillIndexer."""

    def test_make_key(self) -> None:
        """Version-based key format: ``skill_id::version``."""
        key = VersionedTTLCache.make_key("repo-read", version="1.0.0")
        assert key == "repo-read::1.0.0"

    def test_make_key_with_hash(self) -> None:
        """Content-hash fallback when version is not provided."""
        h = VersionedTTLCache.hash_content("hello")
        key = VersionedTTLCache.make_key("repo-read", content_hash=h)
        assert key == f"repo-read::{h}"

    def test_put_get(self) -> None:
        cache = VersionedTTLCache()
        cache.put("k1", {"data": 42})
        assert cache.get("k1") == {"data": 42}

    def test_get_missing(self) -> None:
        """Cache miss must return None, not raise."""
        cache = VersionedTTLCache()
        assert cache.get("missing") is None

    def test_invalidate(self) -> None:
        """After invalidation, the key must report as a miss."""
        cache = VersionedTTLCache()
        cache.put("k1", "val")
        cache.invalidate("k1")
        assert cache.get("k1") is None

    def test_clear(self) -> None:
        """clear() must remove all entries."""
        cache = VersionedTTLCache()
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.clear()
        assert cache.currsize == 0


# ---------------------------------------------------------------------------
# Stage B: metadata_cache shadow-write wiring
# ---------------------------------------------------------------------------

class TestMetadataCacheShadow:
    """Stage B · formalize-cache-layers: metadata_cache is shadow-written
    by build_index; reads still go through _index.  These tests confirm
    the shadow wiring without asserting any read-path behaviour change."""

    def test_metadata_cache_size_matches_index(self, indexer: SkillIndexer) -> None:
        """After build_index, metadata_cache holds exactly one entry per
        indexed skill (shadow-parity invariant)."""
        indexer.build_index()
        assert indexer.metadata_cache.currsize == len(indexer.list_skills())

    def test_custom_metadata_cache_receives_writes(self, skills_dir: Path) -> None:
        """An injected custom metadata_cache instance receives the same
        puts — proves the wiring is not hard-coded to an internal default."""
        custom = VersionedTTLCache()
        indexer = SkillIndexer(skills_dir, metadata_cache=custom)
        assert custom.currsize == 0
        indexer.build_index()
        assert custom.currsize == 2  # repo-read + code-edit from fixture

    def test_legacy_cache_param_emits_deprecation_warning(self, skills_dir: Path) -> None:
        """Passing the legacy positional/keyword `cache=` parameter emits
        DeprecationWarning while preserving backward-compatible behaviour
        (doc cache still works)."""
        with pytest.warns(DeprecationWarning, match="deprecated"):
            indexer = SkillIndexer(skills_dir, cache=VersionedTTLCache())
        indexer.build_index()
        assert indexer.read_skill("repo-read") is not None

    def test_cache_and_doc_cache_conflict_raises(self, skills_dir: Path) -> None:
        """Supplying both legacy `cache=` and new `doc_cache=` is an error
        — they are aliases and must not be combined."""
        with pytest.raises(TypeError, match="aliases"):
            SkillIndexer(
                skills_dir,
                cache=VersionedTTLCache(),
                doc_cache=VersionedTTLCache(),
            )


# ---------------------------------------------------------------------------
# Stage C: read-path migration + spec requirement coverage
# ---------------------------------------------------------------------------

class TestStageC_CacheLayerFormalization:
    """Stage C · formalize-cache-layers: metadata reads flow through the
    formal cache layer with safe rebuild-from-disk fallback.  Each test
    maps to one spec scenario in
    ``openspec/changes/formalize-cache-layers/specs/skill-discovery/spec.md``.
    """

    def test_cache_miss_triggers_clean_rebuild(self, indexer: SkillIndexer) -> None:
        """Spec · Safe fallback · Cache miss triggers a clean rebuild:
        a missing metadata entry is re-parsed from disk and repopulates
        the cache."""
        indexer.build_index()
        assert indexer.metadata_cache.currsize > 0
        indexer.metadata_cache.clear()
        assert indexer.metadata_cache.currsize == 0
        skills = indexer.list_skills()
        assert len(skills) == 2  # repo-read + code-edit from fixture
        assert indexer.metadata_cache.currsize > 0  # rebuilt populated

    def test_metadata_version_bump_supersedes_cache(self, skills_dir: Path) -> None:
        """Spec · Version change · Version bump supersedes a cached metadata
        entry: incrementing a skill's version on disk and refreshing serves
        the new version instead of the previously-cached one."""
        indexer = SkillIndexer(skills_dir)
        indexer.build_index()

        repo_md = skills_dir / "repo-read" / "SKILL.md"
        original = repo_md.read_text(encoding="utf-8")
        bumped = original.replace('version: "1.0.0"', 'version: "2.0.0"')
        repo_md.write_text(bumped, encoding="utf-8")

        indexer.refresh()
        meta = next(s for s in indexer.list_skills() if s.skill_id == "repo-read")
        assert meta.version == "2.0.0"

    def test_doc_version_bump_supersedes_cached_doc(self, skills_dir: Path) -> None:
        """Spec · Version change · Version bump supersedes a cached document:
        when both the frontmatter version and the body change on disk,
        refresh + re-read returns content derived from the new version."""
        indexer = SkillIndexer(skills_dir)
        indexer.build_index()
        first = indexer.read_skill("repo-read")
        assert first is not None
        assert "Read-only exploration" in first.sop

        repo_md = skills_dir / "repo-read" / "SKILL.md"
        original = repo_md.read_text(encoding="utf-8")
        bumped = original.replace('version: "1.0.0"', 'version: "2.0.0"')
        bumped = bumped.replace("Read-only exploration.", "Post-v2 body.")
        repo_md.write_text(bumped, encoding="utf-8")

        indexer.refresh()
        second = indexer.read_skill("repo-read")
        assert second is not None
        assert second.metadata.version == "2.0.0"
        assert "Post-v2 body." in second.sop

    def test_cached_and_rebuilt_metadata_are_identical(
        self, indexer: SkillIndexer
    ) -> None:
        """Spec · Cache-as-performance-layer · Cached and rebuilt values
        are interchangeable: clearing the metadata cache and re-listing
        returns identical content."""
        indexer.build_index()
        before = sorted(
            (m.model_dump() for m in indexer.list_skills()),
            key=lambda d: d["skill_id"],
        )

        indexer.metadata_cache.clear()
        after = sorted(
            (m.model_dump() for m in indexer.list_skills()),
            key=lambda d: d["skill_id"],
        )
        assert before == after

    def test_refresh_clears_both_cache_layers(self, indexer: SkillIndexer) -> None:
        """Spec · Two-layer caching + Refresh · metadata and document
        entries honor a common invalidation surface; one ``refresh()``
        call empties both cache layers within the same operation."""
        indexer.build_index()
        indexer.read_skill("repo-read")  # prime doc cache
        assert indexer.metadata_cache.currsize > 0
        assert indexer.doc_cache.currsize > 0

        indexer.refresh()
        # metadata_cache is repopulated as part of rebuild; doc_cache is
        # left empty until the next read_skill re-populates it.
        assert indexer.doc_cache.currsize == 0

    def test_refresh_failure_drops_stale_entries(self, tmp_path: Path) -> None:
        """Spec · Safe fallback · Refresh failure degrades safely: when a
        skill's source file becomes invalid after an initial successful
        scan, refresh + list_skills must not present the pre-refresh
        cached entry as fresh."""
        skills = tmp_path / "skills"
        skills.mkdir()
        good = skills / "good"
        good.mkdir()
        (good / "SKILL.md").write_text(
            '---\nname: Good\ndescription: "ok"\nversion: "1.0.0"\n---\n\nbody',
            encoding="utf-8",
        )
        indexer = SkillIndexer(skills)
        indexer.build_index()
        assert any(s.skill_id == "good" for s in indexer.list_skills())

        # Corrupt the skill file after initial successful scan.
        (good / "SKILL.md").write_text(
            "---\n: [invalid yaml\n---\nbody", encoding="utf-8"
        )

        indexer.refresh()
        ids_after = {s.skill_id for s in indexer.list_skills()}
        assert "good" not in ids_after  # dropped, not served from pre-refresh cache
