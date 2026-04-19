"""Skill-fixture helpers: resolve and copy mock_ skills into tmp trees."""

from __future__ import annotations

import shutil
from pathlib import Path

from .runtime import fixtures_skills_dir


def copy_fixture_skills(dst_dir: Path, names: list[str]) -> Path:
    """Copy named ``mock_*`` skill directories into ``dst_dir``.

    Creates ``dst_dir`` if missing. Returns the destination path.
    Tests that need to mutate the skills tree (e.g. ``refresh_skills``)
    should work from a tmp copy rather than the checked-in fixture root.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    src_root = fixtures_skills_dir()
    for name in names:
        src = src_root / name
        if not src.is_dir():
            raise FileNotFoundError(f"fixture skill not found: {name}")
        shutil.copytree(src, dst_dir / name, dirs_exist_ok=True)
    return dst_dir
