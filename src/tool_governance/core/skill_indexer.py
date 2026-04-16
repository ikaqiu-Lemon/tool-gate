"""Skill indexer — scans skills/ directory, parses SKILL.md, builds index.

The indexer is the single source of truth for what skills exist.
It walks a directory tree one level deep, expects each subdirectory
to contain a ``SKILL.md`` with YAML frontmatter, and builds an
in-memory ``skill_id → SkillMetadata`` index backed by a
``VersionedTTLCache``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from tool_governance.models.skill import SkillContent, SkillMetadata, StageDefinition
from tool_governance.utils.cache import VersionedTTLCache

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024  # 100 KB — skip oversized SKILL.md files
MAX_DESCRIPTION_LEN = 500
FRONTMATTER_DELIMITER = "---"


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into (frontmatter_dict, body_markdown).

    Returns ``({}, full_text)`` if no valid frontmatter found.

    Contract:
        Raises:
            yaml.YAMLError: If the YAML block between the ``---``
                delimiters is syntactically invalid (re-raised
                explicitly).

        Silences:
            - Missing opening ``---`` delimiter → returns
              ``({}, text)`` silently.
            - Missing closing ``---`` delimiter → same.
            - YAML that parses to a non-dict (e.g. a bare string or
              list) → returns ``({}, text)`` silently.  The caller
              cannot distinguish "no frontmatter" from "frontmatter
              was a non-dict YAML value".
    """
    stripped = text.lstrip()
    if not stripped.startswith(FRONTMATTER_DELIMITER):
        return {}, text

    # Find closing delimiter (must start on its own line).
    after_first = stripped[len(FRONTMATTER_DELIMITER) :]
    end_idx = after_first.find(f"\n{FRONTMATTER_DELIMITER}")
    if end_idx == -1:
        return {}, text

    yaml_block = after_first[:end_idx]
    # Strip the closing "---" line and any leading dashes/newlines
    # that remain after slicing.
    body = after_first[end_idx + len(FRONTMATTER_DELIMITER) + 1 :].lstrip("-").lstrip("\n")

    try:
        data = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        raise  # let caller handle

    if not isinstance(data, dict):
        return {}, text

    return data, body


def _build_metadata(skill_id: str, fm: dict[str, Any], source_path: str) -> SkillMetadata:
    """Construct a SkillMetadata from parsed frontmatter dict.

    Applies defensive coercions: missing keys get defaults, long
    descriptions are truncated, and malformed stage entries are
    silently skipped.

    Contract:
        Raises:
            ValueError / TypeError: If ``fm["default_ttl"]`` is
                present but not convertible to ``int`` (from the
                ``int()`` call, not caught).
            pydantic.ValidationError: If ``risk_level`` is not one
                of the allowed literals (from Pydantic constructor,
                not caught).

        Silences:
            - Descriptions longer than 500 chars are silently
              truncated (no ellipsis marker).
            - Stage entries that are not dicts or lack a
              ``"stage_id"`` key are silently skipped.
            - Missing frontmatter keys are silently defaulted via
              ``.get()`` — ``name`` defaults to ``skill_id``,
              ``risk_level`` to ``"low"``, etc.
    """
    description = str(fm.get("description", ""))
    if len(description) > MAX_DESCRIPTION_LEN:
        description = description[:MAX_DESCRIPTION_LEN]

    # Build stage list defensively — skip entries that don't have
    # the minimum required shape.
    stages: list[StageDefinition] = []
    raw_stages = fm.get("stages", [])
    if isinstance(raw_stages, list):
        for s in raw_stages:
            if isinstance(s, dict) and "stage_id" in s:
                stages.append(
                    StageDefinition(
                        stage_id=s["stage_id"],
                        description=str(s.get("description", "")),
                        allowed_tools=list(s.get("allowed_tools", [])),
                    )
                )

    return SkillMetadata(
        skill_id=skill_id,
        name=str(fm.get("name", skill_id)),
        description=description,
        risk_level=fm.get("risk_level", "low"),
        allowed_tools=list(fm.get("allowed_tools", [])),
        allowed_ops=list(fm.get("allowed_ops", [])),
        stages=stages,
        default_ttl=int(fm.get("default_ttl", 3600)),
        source_path=source_path,
        version=str(fm.get("version", "1.0.0")),
    )


class SkillIndexer:
    """Scans a skills directory, parses SKILL.md files, and maintains a cache."""

    def __init__(self, skills_dir: str | Path, cache: VersionedTTLCache | None = None) -> None:
        self._skills_dir = Path(skills_dir)
        self._cache = cache or VersionedTTLCache()
        self._index: dict[str, SkillMetadata] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_index(self) -> dict[str, SkillMetadata]:
        """Scan skills/ and return skill_id → SkillMetadata mapping.

        The skill_id is derived from the subdirectory name.  Only
        immediate children of ``skills_dir`` that contain a
        ``SKILL.md`` file are considered.

        Contract:
            Silences:
                - If ``skills_dir`` does not exist or is not a
                  directory, logs a warning and returns ``{}``.
                - Non-directory entries in ``skills_dir`` are silently
                  skipped.
                - Subdirectories without a ``SKILL.md`` file are
                  silently skipped.
                - **Any exception** from ``_index_one`` (YAML errors,
                  I/O errors, Pydantic validation, etc.) is caught by
                  a bare ``except Exception``, logged as a warning,
                  and the skill is skipped.  This is the broadest
                  catch in the codebase — even ``KeyboardInterrupt``
                  propagates (it's not an ``Exception`` subclass), but
                  all other failures are swallowed.
        """
        self._index.clear()

        if not self._skills_dir.is_dir():
            logger.warning("Skills directory does not exist: %s", self._skills_dir)
            return self._index

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                self._index_one(skill_dir.name, skill_md)
            except Exception:
                logger.warning("Failed to index skill '%s', skipping", skill_dir.name, exc_info=True)

        return dict(self._index)

    def list_skills(self) -> list[SkillMetadata]:
        """Return all indexed skill metadata.

        Lazily builds the index on first call if the index is empty.

        Contract:
            Silences:
                - If the index is empty because all skills failed to
                  parse (not because ``build_index`` was never called),
                  this method will re-scan the directory on every call
                  — there is no flag to distinguish "never built" from
                  "built but empty".
        """
        if not self._index:
            self.build_index()
        return list(self._index.values())

    def read_skill(self, skill_id: str) -> SkillContent | None:
        """Read and return full skill content (cache-first).

        Contract:
            Raises:
                OSError: If the SKILL.md file exists but is unreadable
                    (from ``read_text``, not caught).

            Silences:
                - Unknown ``skill_id`` (not in the index) → returns
                  ``None``.
                - SKILL.md file deleted after indexing → returns
                  ``None``.
                - ``yaml.YAMLError`` during re-parse of frontmatter
                  is caught; the raw file text is used as the SOP
                  body instead.  The caller receives a
                  ``SkillContent`` with the full raw text as ``sop``
                  and no indication that parsing failed.
        """
        meta = self._index.get(skill_id)
        if meta is None:
            return None

        cache_key = VersionedTTLCache.make_key(skill_id, version=meta.version)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        skill_md = Path(meta.source_path)
        if not skill_md.is_file():
            return None

        raw = skill_md.read_text(encoding="utf-8")
        try:
            _, body = _parse_frontmatter(raw)
        except yaml.YAMLError:
            # Frontmatter is corrupt on re-read; fall back to the
            # entire file as the SOP body.
            body = raw

        content = SkillContent(metadata=meta, sop=body)
        self._cache.put(cache_key, content)
        return content

    def refresh(self) -> int:
        """Clear caches and rebuild index. Return skill count."""
        self._cache.clear()
        self.build_index()
        return len(self._index)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _index_one(self, skill_id: str, path: Path) -> None:
        """Parse a single SKILL.md and add its metadata to the index.

        Contract:
            Raises:
                yaml.YAMLError: If the frontmatter YAML is
                    syntactically invalid (from ``_parse_frontmatter``,
                    not caught — propagates to ``build_index``'s
                    ``except Exception`` handler).
                OSError: If the file cannot be read.

            Silences:
                - Files exceeding ``MAX_FILE_SIZE`` (100 KB) are
                  silently skipped with a log warning.
                - Files with no parseable frontmatter (``fm`` is
                  empty) are silently skipped with a log warning.
        """
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning("SKILL.md for '%s' exceeds %d bytes, skipping", skill_id, MAX_FILE_SIZE)
            return

        raw = path.read_text(encoding="utf-8")
        try:
            fm, _ = _parse_frontmatter(raw)
        except yaml.YAMLError:
            logger.warning("Invalid YAML in '%s', skipping", skill_id, exc_info=True)
            return

        if not fm:
            logger.warning("No frontmatter found in '%s', skipping", skill_id)
            return

        meta = _build_metadata(skill_id, fm, source_path=str(path))
        self._index[skill_id] = meta
