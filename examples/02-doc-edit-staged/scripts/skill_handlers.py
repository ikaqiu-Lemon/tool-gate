"""Skill handlers for example 02 (doc-edit-staged).

This module registers handlers for the yuque-doc-edit skill's operations.
"""

from __future__ import annotations

from typing import Any

from tool_governance.core.skill_executor import register_handler


def _yuque_doc_edit_append(doc_id: str, content: str, **_: Any) -> dict[str, Any]:
    """Handler for yuque-doc-edit.append operation.

    In a real implementation, this would:
    1. Fetch the current document via yuque_get_doc
    2. Append the new content
    3. Write back via yuque_update_doc

    For this demo, we return a mock success response.
    """
    return {
        "ok": True,
        "doc_id": doc_id,
        "operation": "append",
        "content_length": len(content),
        "message": f"成功追加 {len(content)} 字符到文档 {doc_id}"
    }


def _yuque_doc_edit_preview(doc_id: str, **_: Any) -> dict[str, Any]:
    """Handler for yuque-doc-edit.preview operation.

    Returns a preview of the document before editing.
    """
    return {
        "ok": True,
        "doc_id": doc_id,
        "preview": {
            "title": "RAG 技术概览 v2",
            "last_modified": "2026-04-19T10:30:00+08:00",
            "word_count": 3500,
            "sections": ["概述", "向量召回", "生成阶段", "评估方法"]
        }
    }


# Register handlers
register_handler("yuque-doc-edit", "append", _yuque_doc_edit_append)
register_handler("yuque-doc-edit", "preview", _yuque_doc_edit_preview)
