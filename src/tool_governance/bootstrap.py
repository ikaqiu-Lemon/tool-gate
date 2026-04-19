"""Bootstrap — assembles the GovernanceRuntime from configuration.

Single entry point for wiring all governance modules together.
``create_governance_runtime`` is called once per process (typically
by ``_get_runtime()`` in ``hook_handler.py``) and returns a fully
initialised ``GovernanceRuntime`` facade.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tool_governance.core.grant_manager import GrantManager
from tool_governance.core.observability import LangfuseTracer, create_tracer
from tool_governance.core.policy_engine import PolicyEngine
from tool_governance.core.prompt_composer import PromptComposer
from tool_governance.core.skill_indexer import SkillIndexer
from tool_governance.core.state_manager import StateManager
from tool_governance.core.tool_rewriter import ToolRewriter
from tool_governance.models.policy import GovernancePolicy
from tool_governance.storage.sqlite_store import SQLiteStore
from tool_governance.utils.cache import VersionedTTLCache


class GovernanceRuntime:
    """Facade holding all governance modules.

    Pure container — no logic of its own.  All fields are public so
    that hook handlers can orchestrate the modules directly.
    """

    def __init__(
        self,
        store: SQLiteStore,
        indexer: SkillIndexer,
        state_manager: StateManager,
        policy_engine: PolicyEngine,
        grant_manager: GrantManager,
        tool_rewriter: ToolRewriter,
        prompt_composer: PromptComposer,
        policy: GovernancePolicy,
        tracer: LangfuseTracer | None = None,
    ) -> None:
        self.store = store
        self.indexer = indexer
        self.state_manager = state_manager
        self.policy_engine = policy_engine
        self.grant_manager = grant_manager
        self.tool_rewriter = tool_rewriter
        self.prompt_composer = prompt_composer
        self.policy = policy
        self.tracer = tracer or LangfuseTracer(client=None)


def load_policy(config_dir: str | Path) -> GovernancePolicy:
    """Load governance policy from YAML config, falling back to defaults.

    Contract:
        Raises:
            yaml.YAMLError: If the YAML file exists but is
                syntactically invalid (from ``yaml.safe_load``,
                not caught).
            pydantic.ValidationError: If the YAML is valid but
                contains values that violate ``GovernancePolicy``
                field constraints (from ``model_validate``,
                not caught).

        Silences:
            - Missing config file → returns ``GovernancePolicy()``
              with all defaults.  No log or signal.
            - YAML that parses to a non-dict (e.g. a bare string)
              → returns ``GovernancePolicy()`` silently.
    """
    config_path = Path(config_dir) / "default_policy.yaml"
    if not config_path.is_file():
        return GovernancePolicy()
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return GovernancePolicy()
    return GovernancePolicy.model_validate(data)


def create_governance_runtime(
    data_dir: str | Path,
    skills_dir: str | Path,
    config_dir: str | Path | None = None,
) -> GovernanceRuntime:
    """Factory: assemble all modules into a GovernanceRuntime.

    Contract:
        Raises:
            sqlite3.OperationalError: If ``SQLiteStore`` cannot
                create or open the database in ``data_dir``
                (not caught).
            yaml.YAMLError / pydantic.ValidationError: From
                ``load_policy`` if the config file is corrupt
                (not caught).

        Silences:
            - If ``config_dir`` is ``None``, silently falls back to
              ``data_dir`` as the config directory.  The caller has
              no way to know the policy was loaded from a fallback
              location.
    """
    tracer = create_tracer()
    store = SQLiteStore(data_dir, tracer=tracer)
    cache = VersionedTTLCache(maxsize=100, ttl=300)
    indexer = SkillIndexer(skills_dir, cache)
    state_manager = StateManager(store)
    # Fall back to data_dir for config if no explicit config_dir given.
    policy = load_policy(config_dir or data_dir)
    policy_engine = PolicyEngine(policy)
    grant_manager = GrantManager(store)
    # Wire the global blocked_tools list from the policy into the
    # rewriter's deny-set at construction time.
    tool_rewriter = ToolRewriter(blocked_tools=policy.blocked_tools)
    prompt_composer = PromptComposer()

    return GovernanceRuntime(
        store=store,
        indexer=indexer,
        state_manager=state_manager,
        policy_engine=policy_engine,
        grant_manager=grant_manager,
        tool_rewriter=tool_rewriter,
        prompt_composer=prompt_composer,
        policy=policy,
        tracer=tracer,
    )
