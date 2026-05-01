---
name: Yuque Comment Sync
description: "演示用 · Yuque 风格评论同步:拉取指定文档的评论流,供后续分析。"
risk_level: low
version: "0.1.0"
default_ttl: 3600
allowed_tools:
  - yuque_list_comments
  - yuque_get_doc
allowed_ops:
  - sync_comments
---

# Yuque Comment Sync

演示用只读技能;Alice 的同事 Bob 在任务中途推送进来,用于 `refresh_skills` 插曲。

## 触发场景

<!-- Phase B 前补齐:列出触发该技能的自然语言样例 -->

## 操作流程

<!-- Phase B 前补齐:拉评论 → 按作者 / 时间排序 → 输出摘要 -->

## 错误处理

<!-- Phase B 前补齐:空评论、权限不足等降级 -->
