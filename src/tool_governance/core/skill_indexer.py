"""Skill indexer — scans skills/ directory, parses SKILL.md, builds index.

The indexer is the single source of truth for what skills exist.
It walks a directory tree one level deep, expects each subdirectory
to contain a ``SKILL.md`` with YAML frontmatter, and maintains two
explicit cache layers sharing one ``VersionedTTLCache`` contract:

- ``metadata_cache`` — holds :class:`SkillMetadata` objects keyed by
  ``skill_id::version``; primary performance layer for catalog lookups.
- ``doc_cache`` — holds :class:`SkillContent` objects produced by
  :meth:`SkillIndexer.read_skill`, keyed the same way.

Cache is a performance layer, not a source of truth: every cached
value is reproducible by re-reading the underlying skill file.
Lookups that miss the cache fall back to rebuild-from-disk via the
lightweight ``_indexed_skills`` registry, which maps each known
``skill_id`` to the ``(version, source_path)`` tuple produced by the
most recent scan.  The registry is the ground truth of "what exists";
the metadata cache is the performance layer on top of it.
"""

from __future__ import annotations

import logging
import warnings
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
                        allowed_next_stages=list(s.get("allowed_next_stages", [])),
                    )
                )

    # Extract initial_stage if present
    initial_stage = fm.get("initial_stage")
    if initial_stage is not None:
        initial_stage = str(initial_stage)

    return SkillMetadata(
        skill_id=skill_id,
        name=str(fm.get("name", skill_id)),
        description=description,
        risk_level=fm.get("risk_level", "low"),
        allowed_tools=list(fm.get("allowed_tools", [])),
        allowed_ops=list(fm.get("allowed_ops", [])),
        stages=stages,
        initial_stage=initial_stage,
        default_ttl=int(fm.get("default_ttl", 3600)),
        source_path=source_path,
        version=str(fm.get("version", "1.0.0")),
    )


class SkillIndexer:
    """Scans a skills directory, parses SKILL.md files, and maintains two
    cache layers (metadata + documents) sharing one key / TTL / invalidate
    contract on top of a lightweight ``_indexed_skills`` registry."""

    def __init__(
        self,
        skills_dir: str | Path,
        cache: VersionedTTLCache | None = None,
        *,
        doc_cache: VersionedTTLCache | None = None,
        metadata_cache: VersionedTTLCache | None = None,
    ) -> None:
        """Construct a SkillIndexer.

        Parameters:
            skills_dir: Root directory containing one subdirectory per
                skill (each with a ``SKILL.md``).
            cache: **Deprecated.** Legacy alias for ``doc_cache``.
                Pass ``doc_cache=`` (keyword-only) in new code.  Using
                ``cache`` emits :class:`DeprecationWarning`.
            doc_cache: Cache for parsed ``SkillContent`` objects
                (``read_skill`` results).  Defaults to a fresh
                :class:`VersionedTTLCache`.
            metadata_cache: Cache for ``SkillMetadata`` objects produced
                by the directory scan.  Defaults to a fresh
                :class:`VersionedTTLCache`.

        Contract:
            Raises:
                TypeError: If both ``cache`` and ``doc_cache`` are
                    supplied simultaneously.  They are aliases and
                    must not be used together.

            Silences:
                - ``None`` for either cache triggers default
                  construction; callers never need to special-case
                  wiring.
        """
        self._skills_dir = Path(skills_dir)

        if cache is not None and doc_cache is not None:
            raise TypeError(
                "SkillIndexer: 'cache' (deprecated) and 'doc_cache' are aliases; "
                "pass only one."
            )
        if cache is not None:
            warnings.warn(
                "SkillIndexer('cache=...') is deprecated; use 'doc_cache=...' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            doc_cache = cache

        self._doc_cache: VersionedTTLCache = doc_cache or VersionedTTLCache()
        self._metadata_cache: VersionedTTLCache = metadata_cache or VersionedTTLCache()
        # Authoritative "what was discovered last scan" registry.
        # skill_id → (version, source_path).  Much smaller than the
        # metadata payload itself; serves as the ground truth so that
        # cache eviction does not mean "skill disappeared".
        self._indexed_skills: dict[str, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def metadata_cache(self) -> VersionedTTLCache:
        """Formal metadata cache keyed by ``skill_id::version``.

        Primary performance layer for ``SkillMetadata`` lookups.  Read
        paths hit this cache first and fall back to disk via the
        ``_indexed_skills`` registry on miss.
        """
        return self._metadata_cache

    @property
    def doc_cache(self) -> VersionedTTLCache:
        """Formal document cache used by ``read_skill``."""
        return self._doc_cache

    def build_index(self) -> dict[str, SkillMetadata]:
        """Scan skills/ and return skill_id → SkillMetadata mapping.

        Clears the ``_indexed_skills`` registry and the metadata cache
        before scanning.  The document cache is **not** cleared here —
        lazy rebuilds triggered by an empty registry should not evict
        unrelated SOP bodies.  Only :meth:`refresh` clears both layers.

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
                  and the skill is skipped.
        """
        self._indexed_skills.clear()
        self._metadata_cache.clear()

        result: dict[str, SkillMetadata] = {}

        if not self._skills_dir.is_dir():
            logger.warning("Skills directory does not exist: %s", self._skills_dir)
            return result

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                meta = self._index_one(skill_dir.name, skill_md)
            except Exception:
                logger.warning(
                    "Failed to index skill '%s', skipping",
                    skill_dir.name,
                    exc_info=True,
                )
                continue
            if meta is not None:
                result[skill_dir.name] = meta

        return result

    def list_skills(self) -> list[SkillMetadata]:
        """Return all indexed skill metadata.

        Lazily builds the index on first call if the registry is empty.
        Each entry is served from ``metadata_cache`` on hit, or
        re-parsed from disk on miss (safe-fallback invariant).

        Contract:
            Silences:
                - If the registry is empty because all skills failed to
                  parse (not because ``build_index`` was never called),
                  this method will re-scan the directory on every call.
        """
        if not self._indexed_skills:
            self.build_index()
        result: list[SkillMetadata] = []
        for skill_id in list(self._indexed_skills.keys()):
            meta = self._get_metadata(skill_id)
            if meta is not None:
                result.append(meta)
        return result

    def read_skill(self, skill_id: str) -> SkillContent | None:
        """Read and return full skill content (cache-first).

        Flow: resolve metadata via ``_get_metadata`` (cache hit or disk
        rehydrate).  Then look up the SOP body in ``doc_cache``; if
        absent, re-read the SKILL.md file, parse the body, and populate
        the cache.

        Contract:
            Raises:
                OSError: If the SKILL.md file exists but is unreadable
                    during doc-body re-read (not caught).

            Silences:
                - Unknown ``skill_id`` (not in registry) → ``None``.
                - SKILL.md file deleted after indexing → ``None``.
                - ``yaml.YAMLError`` during re-parse of frontmatter
                  on the doc-read path is caught; the raw file text
                  is used as the SOP body instead.
        """
        meta = self._get_metadata(skill_id)
        if meta is None:
            return None

        cache_key = VersionedTTLCache.make_key(skill_id, version=meta.version)
        cached = self._doc_cache.get(cache_key)
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
        self._doc_cache.put(cache_key, content)
        return content

    def refresh(self) -> int:
        """Clear both caches and rebuild the index. Return skill count.

        Metadata cache and document cache are cleared within the same
        refresh call — no pre-refresh entry may satisfy a lookup that
        completes after this method returns.
        """
        self._metadata_cache.clear()
        self._doc_cache.clear()
        self.build_index()
        return len(self._indexed_skills)

    def current_index(self) -> dict[str, SkillMetadata]:
        """Return a snapshot of the current index without a rescan.

        Uses cache-first lookup per skill with rehydrate fallback, so
        the returned dict reflects the registry's current composition
        even if some entries were evicted from the metadata cache.
        """
        result: dict[str, SkillMetadata] = {}
        for skill_id in list(self._indexed_skills.keys()):
            meta = self._get_metadata(skill_id)
            if meta is not None:
                result[skill_id] = meta
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_metadata(self, skill_id: str) -> SkillMetadata | None:
        """Cache-first metadata lookup with rebuild-from-disk fallback.

        Returns ``None`` if ``skill_id`` is not in the registry.
        Otherwise, returns the cached metadata; on cache miss re-parses
        the source file and repopulates the cache.  If rehydrate itself
        fails (source unreadable, frontmatter invalid, etc.), the
        registry entry is pruned so that subsequent lookups do not
        present a stale cached value as fresh.
        """
        entry = self._indexed_skills.get(skill_id)
        if entry is None:
            return None
        version, source_path = entry
        cache_key = VersionedTTLCache.make_key(skill_id, version=version)
        meta = self._metadata_cache.get(cache_key)
        if meta is not None:
            return meta  # type: ignore[no-any-return]

        # Cache miss: rebuild from disk (safe-fallback invariant).
        try:
            rebuilt = self._parse_skill_file(skill_id, Path(source_path))
        except Exception:  # noqa: BLE001 — rehydrate failure must not crash
            logger.warning(
                "Rehydrate failed for '%s'; dropping from registry",
                skill_id,
                exc_info=True,
            )
            self._indexed_skills.pop(skill_id, None)
            return None

        if rebuilt is None:
            # Skippable error on re-read (oversized / invalid / missing).
            # Drop so we don't keep pointing at a now-unreadable source.
            self._indexed_skills.pop(skill_id, None)
            return None

        # Version drift: the file has been edited since the last scan.
        # Update the registry so future lookups use the new key, and
        # store under the new version.  The old version's key, if still
        # in the cache, is unreachable via the registry and will TTL out.
        if rebuilt.version != version:
            self._indexed_skills[skill_id] = (rebuilt.version, source_path)
            cache_key = VersionedTTLCache.make_key(
                skill_id, version=rebuilt.version
            )
        self._metadata_cache.put(cache_key, rebuilt)
        return rebuilt

    def _index_one(self, skill_id: str, path: Path) -> SkillMetadata | None:
        """Parse one SKILL.md and populate both registry and metadata cache.

        Returns the parsed metadata, or ``None`` if the file was
        skippable (oversized / invalid YAML / missing frontmatter).
        """
        meta = self._parse_skill_file(skill_id, path)
        if meta is None:
            return None
        self._indexed_skills[skill_id] = (meta.version, str(path))
        self._metadata_cache.put(
            VersionedTTLCache.make_key(skill_id, version=meta.version),
            meta,
        )
        return meta

    def _parse_skill_file(
        self, skill_id: str, path: Path
    ) -> SkillMetadata | None:
        """Parse one SKILL.md, applying size and safety limits.

        Shared by the scan path (``_index_one``) and the cache-miss
        rehydrate path (``_get_metadata``).  Returns ``None`` for
        skippable errors (oversized file, invalid YAML, missing
        frontmatter); propagates unexpected errors (OSError on read,
        Pydantic validation errors) so outer ``except Exception``
        handlers surface them.

        Contract:
            Raises:
                OSError: If ``path`` cannot be stat'd or read (not
                    caught — callers must handle).
                yaml.YAMLError: Only if it escapes
                    ``_parse_frontmatter``'s own catch — currently
                    ``_parse_frontmatter`` re-raises on invalid YAML,
                    which this function catches.

            Silences:
                - File exceeding ``MAX_FILE_SIZE`` → ``None`` + warning.
                - Invalid YAML frontmatter → ``None`` + warning.
                - Missing or non-dict frontmatter → ``None`` + warning.
        """
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(
                "SKILL.md for '%s' exceeds %d bytes, skipping",
                skill_id,
                MAX_FILE_SIZE,
            )
            return None

        raw = path.read_text(encoding="utf-8")
        try:
            fm, _ = _parse_frontmatter(raw)
        except yaml.YAMLError:
            logger.warning("Invalid YAML in '%s', skipping", skill_id, exc_info=True)
            return None

        if not fm:
            logger.warning("No frontmatter found in '%s', skipping", skill_id)
            return None

        return _build_metadata(skill_id, fm, source_path=str(path))
