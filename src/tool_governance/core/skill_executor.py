"""Skill executor — registration-based dispatch table for run_skill_action.

Skills register their operation handlers at import time via
``register_handler``.  At runtime, ``dispatch`` looks up the
(skill_id, op) pair and invokes the matching handler.
"""

from __future__ import annotations

from typing import Any, Callable

# Dispatch table: (skill_id, op) → handler function.
# Populated at module-import time by ``register_handler`` calls.
SKILL_HANDLERS: dict[tuple[str, str], Callable[..., dict[str, Any]]] = {}


def register_handler(skill_id: str, op: str, handler: Callable[..., dict[str, Any]]) -> None:
    """Register a handler for a (skill_id, op) pair.

    Contract:
        Silences:
            - If a handler is already registered for the same
              ``(skill_id, op)`` pair, it is silently overwritten.
              The caller has no way to detect the collision.
    """
    SKILL_HANDLERS[(skill_id, op)] = handler


def dispatch(skill_id: str, op: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to registered handler.

    .. note:: The existing docstring says "Raises KeyError" but the
       actual code returns an error dict instead of raising.

    Contract:
        Raises:
            TypeError: If the handler's signature does not accept
                the keys in ``args`` (implicit — from ``**args``
                unpacking).  Any other exception raised by the
                handler propagates uncaught.

        Silences:
            - A missing handler returns
              ``{"error": "No handler for ..."}`` instead of raising.
              The caller must inspect the ``"error"`` key to
              distinguish this from a successful result that happens
              to contain an ``"error"`` key.
    """
    handler = SKILL_HANDLERS.get((skill_id, op))
    if handler is None:
        return {"error": f"No handler for {skill_id}.{op}"}
    return handler(**args)


# ---------------------------------------------------------------------------
# Built-in example handlers (stubs — delegate to Claude tools in practice)
# ---------------------------------------------------------------------------

def _repo_read_search(pattern: str = "", **_: Any) -> dict[str, Any]:
    return {"info": f"repo-read.search: pattern='{pattern}' (stub — actual search via Claude tools)"}


def _repo_read_read_file(path: str = "", **_: Any) -> dict[str, Any]:
    return {"info": f"repo-read.read_file: path='{path}' (stub)"}


def _code_edit_analyze(path: str = "", **_: Any) -> dict[str, Any]:
    return {"info": f"code-edit.analyze: path='{path}' (stub)"}


def _code_edit_edit(path: str = "", content: str = "", **_: Any) -> dict[str, Any]:
    return {"info": f"code-edit.edit: path='{path}' (stub)"}


# Register built-in handlers
register_handler("repo-read", "search", _repo_read_search)
register_handler("repo-read", "read_file", _repo_read_read_file)
register_handler("code-edit", "analyze", _code_edit_analyze)
register_handler("code-edit", "edit", _code_edit_edit)
