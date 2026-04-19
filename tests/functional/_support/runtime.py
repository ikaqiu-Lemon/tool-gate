"""Runtime factory for functional tests.

Builds an isolated ``GovernanceRuntime`` against a tmp data/config dir
and the mock fixture skills tree, then injects it into the
``hook_handler`` and ``mcp_server`` module-level singletons so the
production entry points use the test runtime.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import tool_governance.hook_handler as hh
import tool_governance.mcp_server as mcp_server
from tool_governance.bootstrap import create_governance_runtime

_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures"

DEFAULT_POLICY_YAML = (
    "default_risk_thresholds:\n"
    "  low: auto\n"
    "  medium: reason\n"
    "  high: approval\n"
    "default_ttl: 3600\n"
    "blocked_tools: []\n"
)
# Legacy private alias retained so nothing in-tree breaks.
_DEFAULT_POLICY_YAML = DEFAULT_POLICY_YAML


def fixtures_skills_dir() -> Path:
    """Return the checked-in ``mock_*`` skills fixture root."""
    return _FIXTURES_ROOT / "skills"


def fixtures_policies_dir() -> Path:
    """Return the checked-in policy fixture root (``default.yaml`` etc.)."""
    return _FIXTURES_ROOT / "policies"


def make_runtime(
    tmp_path: Path,
    *,
    skills_dir: Path | None = None,
    policy_yaml: str = DEFAULT_POLICY_YAML,
    policy_file: Path | None = None,
):
    """Build an isolated runtime and inject it into hook+mcp singletons.

    ``policy_file``, if provided, wins over ``policy_yaml`` — its text
    is copied verbatim into ``tmp_path/config/default_policy.yaml``
    (the same on-disk path ``bootstrap.load_policy`` reads), so tests
    exercise ``PolicyEngine`` through the real loader.  No in-memory
    shortcut, no monkeypatching of the engine.

    Caller MUST call :func:`teardown_runtime` (or use
    :func:`runtime_context`) so the next test starts clean.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    if policy_file is not None:
        policy_text = Path(policy_file).read_text(encoding="utf-8")
    else:
        policy_text = policy_yaml
    (config_dir / "default_policy.yaml").write_text(policy_text, encoding="utf-8")

    skills = skills_dir or fixtures_skills_dir()
    rt = create_governance_runtime(str(data_dir), str(skills), str(config_dir))
    hh._runtime = rt
    mcp_server._runtime = rt
    return rt


def teardown_runtime() -> None:
    hh._runtime = None
    mcp_server._runtime = None


@contextlib.contextmanager
def runtime_context(tmp_path: Path, **kwargs):
    rt = make_runtime(tmp_path, **kwargs)
    try:
        yield rt
    finally:
        teardown_runtime()
