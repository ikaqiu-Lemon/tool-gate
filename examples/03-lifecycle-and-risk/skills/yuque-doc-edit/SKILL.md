---
name: Yuque Doc Edit
description: "演示用 · Yuque 风格文档编辑(样例 03 中复刻以演示主动 disable)。"
risk_level: medium
version: "0.1.0"
default_ttl: 3600
allowed_ops:
  - analyze
  - write_back
stages:
  - stage_id: analysis
    description: "只读分析阶段。"
    allowed_tools:
      - yuque_get_doc
      - yuque_list_docs
  - stage_id: execution
    description: "写入阶段。"
    allowed_tools:
      - yuque_get_doc
      - yuque_update_doc
---

# Yuque Doc Edit

样例 03 中的复刻副本,用于演示 `disable_skill` 导致 `grant.revoke → skill.disable` 的审计顺序。

## 触发场景

<!-- Phase B 前补齐 -->

## 操作流程

<!-- Phase B 前补齐 -->

## 错误处理

<!-- Phase B 前补齐 -->
