"""Internal helpers for functional tests (Stage A skeleton).

Modules added in later phases:

* ``runtime.py`` — tmp-dir ``GovernanceRuntime`` factory with
  ``hook_handler._runtime`` / ``mcp_server._runtime`` injection.
* ``events.py`` — canonical hook event JSON builders.
* ``audit.py`` — audit-log query helpers.
* ``stdio.py`` — subprocess lifecycle for ``tg-hook``, ``tg-mcp``, and the
  ``mock_*_stdio`` servers.
* ``skills.py`` — fixture-path resolver and tmp-tree copy helper.
"""
