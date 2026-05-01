"""Skill handlers for example 03 - lifecycle-and-risk.

This module registers handlers for skills used in this example.
"""

from tool_governance.skill_registry import register_skill_handler


@register_skill_handler("yuque-knowledge-link")
async def handle_yuque_knowledge_link(op: str, args: dict) -> dict:
    """Handle yuque-knowledge-link skill operations."""
    if op == "relate":
        doc_ids = args.get("doc_ids", [])
        return {
            "report": {
                "documents_analyzed": len(doc_ids),
                "relationships": [
                    {"from": "rag-overview-v2", "to": "vector-recall-best", "type": "references"},
                    {"from": "rag-overview-v2", "to": "rag-eval-playbook", "type": "related"},
                ],
                "knowledge_gaps": [
                    "缺少关于 RAG 在生产环境的部署案例"
                ]
            }
        }
    return {"error": f"Unknown operation: {op}"}


@register_skill_handler("yuque-doc-edit")
async def handle_yuque_doc_edit(op: str, args: dict) -> dict:
    """Handle yuque-doc-edit skill operations."""
    if op == "update":
        doc_id = args.get("doc_id")
        return {
            "success": True,
            "doc_id": doc_id,
            "version": 6
        }
    return {"error": f"Unknown operation: {op}"}


@register_skill_handler("yuque-bulk-delete")
async def handle_yuque_bulk_delete(op: str, args: dict) -> dict:
    """Handle yuque-bulk-delete skill operations."""
    if op == "delete_batch":
        doc_ids = args.get("doc_ids", [])
        return {
            "deleted_count": len(doc_ids),
            "failed": []
        }
    return {"error": f"Unknown operation: {op}"}
