"""LRU/TTL cache wrapper with version-aware keys."""

from __future__ import annotations

import hashlib
from typing import Any

from cachetools import TTLCache


class VersionedTTLCache:
    """A TTLCache whose keys incorporate a content version/hash.

    This ensures that if a skill file changes on disk, a stale cached
    entry is never returned (even within the TTL window) because the
    key itself differs.

    Design note: the cache never explicitly evicts old-version entries.
    They simply expire when the underlying TTLCache's TTL elapses or
    the LRU policy reclaims space.
    """

    def __init__(self, maxsize: int = 100, ttl: float = 300) -> None:
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(skill_id: str, version: str | None = None, content_hash: str | None = None) -> str:
        """Build a cache key from skill_id + version or content hash.

        Contract:
            Preconditions:
                - `skill_id` must be a non-empty string.  If empty, the
                  key degenerates to "::<suffix>" which is technically
                  valid but will collide across skills (silent wrong
                  result — no error raised).

            Silences:
                - When both `version` and `content_hash` are None the
                  suffix falls back to the literal "unknown".  The
                  caller gets a usable key, but all None-versioned
                  entries for the same skill_id share one slot —
                  potentially returning stale data.
        """
        # Prefer version over content_hash; fall back to "unknown" so
        # callers always receive a valid key even without version info.
        suffix = version or content_hash or "unknown"
        return f"{skill_id}::{suffix}"

    @staticmethod
    def hash_content(content: str) -> str:
        """Return a short SHA-256 hex digest of *content*.

        Contract:
            Preconditions:
                - `content` must be a str.  Passing bytes raises
                  AttributeError on the `.encode()` call (implicit).
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or None on miss/expiry."""
        value = self._cache.get(key)
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def put(self, key: str, value: Any) -> None:
        """Insert or overwrite *key* in the cache.

        Contract:
            Silences:
                - If the cache is at capacity, the least-recently-used
                  entry is silently evicted by cachetools.  No error or
                  signal is raised to the caller.
        """
        self._cache[key] = value

    def invalidate(self, key: str) -> None:
        """Remove *key* if present; no-op if absent."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def currsize(self) -> int:
        return int(self._cache.currsize)
