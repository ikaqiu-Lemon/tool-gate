"""Shared pytest fixtures for the functional test suite."""

from __future__ import annotations

import pytest


@pytest.fixture
def session_id(request) -> str:
    """Per-test session_id so audit queries never cross tests."""
    return f"func-{request.node.name}"
