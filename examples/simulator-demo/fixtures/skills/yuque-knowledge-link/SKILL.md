---
skill_id: yuque-knowledge-link
name: Yuque Knowledge Link
description: Search and link Yuque knowledge base articles (no-stage skill demonstrating fallback behavior)
risk_level: low
allowed_tools:
  - yuque_search
  - yuque_get_doc
---

# Yuque Knowledge Link

## Purpose

Demonstrates no-stage skill behavior with `allowed_tools` fallback.

This skill has no `stages` field, so the runtime uses the top-level `allowed_tools` for all operations. This demonstrates backward compatibility with pre-Stage-first skills.

## Operations

- **Search** — Find relevant knowledge base articles
- **Read** — Retrieve article content for linking

## Allowed Tools

- `yuque_search` — Search for documents
- `yuque_get_doc` — Read document content

## Metadata

```yaml
skill_id: yuque-knowledge-link
name: Yuque Knowledge Link
description: Search and link Yuque knowledge base articles
risk_level: low
allowed_tools:
  - yuque_search
  - yuque_get_doc
# No stages field — demonstrates no-stage fallback behavior
```

## Stage-first Governance Behaviors Demonstrated

- **No-stage fallback**: Skill has no `stages` field, runtime uses top-level `allowed_tools`
- **Backward compatibility**: Pre-Stage-first skills continue to work without modification
- **No stage transitions**: `change_stage` not applicable, skill operates with fixed tool set
