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
