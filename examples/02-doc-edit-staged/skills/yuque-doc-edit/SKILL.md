---
name: Yuque Doc Edit
description: "演示用 · Yuque 风格文档编辑:分阶段(analysis → execution),写回前强制阅读最新版本。"
risk_level: medium
version: "0.1.0"
default_ttl: 3600
allowed_ops:
  - analyze
  - write_back
stages:
  - stage_id: analysis
    description: "只读分析阶段:在写入之前拉最新正文,避免并发覆盖。"
    allowed_tools:
      - yuque_get_doc
      - yuque_list_docs
  - stage_id: execution
    description: "写入阶段:在 analysis 已读过最新正文后才进入。"
    allowed_tools:
      - yuque_get_doc
      - yuque_update_doc
---

# Yuque Doc Edit

演示用技能:用分阶段方式把关联报告的"相关文档"区块写回指定文档。

## 触发场景

<!-- Phase B 前补齐:列出 "把关联报告写回文档"、"追加相关文档区块" 等触发语 -->

## 操作流程

<!-- Phase B 前补齐:analysis 阶段 yuque_get_doc 拉最新正文 → 本地生成追加区块 → change_stage execution → yuque_update_doc 写回(只追加,不覆盖)-->

## 错误处理

<!-- Phase B 前补齐:并发冲突、写回 4xx、版本不一致等;失败时降级为"仅输出建议,不落盘" -->
