---
name: Yuque Bulk Delete
description: "演示用 · Yuque 风格批量删除文档,高风险,须审批。"
risk_level: high
version: "0.1.0"
default_ttl: 600
allowed_tools:
  - yuque_list_docs
  - yuque_delete_doc
allowed_ops:
  - bulk_delete
---

# Yuque Bulk Delete

演示用高风险技能。在本样例中用于证明**两层防线**:策略层 `approval_required` + 工具层 `blocked_tools`。

## 触发场景

<!-- Phase B 前补齐:清理过期归档、批量作废等 -->

## 操作流程

<!-- Phase B 前补齐:列举待删 → 审批通过后执行 → 每批限流;本样例中永远到不了执行阶段 -->

## 错误处理

<!-- Phase B 前补齐:审批拒绝、部分失败、回滚策略 -->
