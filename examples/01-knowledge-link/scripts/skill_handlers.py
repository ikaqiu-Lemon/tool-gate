"""Skill handlers for example 01 (knowledge-link).

This module registers handlers for the yuque-knowledge-link skill's operations.
It should be imported by the demo script to make the handlers available.
"""

from __future__ import annotations

from typing import Any

from tool_governance.core.skill_executor import register_handler


def _yuque_knowledge_link_relate(doc_ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
    """Handler for yuque-knowledge-link.relate operation.

    In a real implementation, this would:
    1. Fetch the documents via yuque_get_doc
    2. Analyze their content to find relationships
    3. Generate a linkage report

    For this demo, we return a mock report structure.
    """
    if doc_ids is None:
        doc_ids = ["rag-overview-v2", "vector-recall-best", "rag-eval-playbook"]

    return {
        "ok": True,
        "report": {
            "title": "RAG 笔记关联分析报告",
            "documents_analyzed": len(doc_ids),
            "doc_ids": doc_ids,
            "relationships": [
                {
                    "from": "rag-overview-v2",
                    "to": "vector-recall-best",
                    "type": "implements",
                    "description": "向量召回实践文档实现了总览中提到的召回阶段"
                },
                {
                    "from": "rag-overview-v2",
                    "to": "rag-eval-playbook",
                    "type": "evaluated_by",
                    "description": "评测 Playbook 提供了总览中召回阶段的质量保证方法"
                }
            ],
            "knowledge_gaps": [
                "缺少生成阶段的详细实践文档",
                "缺少端到端性能优化指南",
                "缺少失败案例分析和调试方法"
            ],
            "recommendations": [
                "补充生成阶段的最佳实践文档",
                "添加完整的 RAG pipeline 性能调优指南",
                "建立故障排查知识库"
            ]
        }
    }


# Register the handler
register_handler("yuque-knowledge-link", "relate", _yuque_knowledge_link_relate)
