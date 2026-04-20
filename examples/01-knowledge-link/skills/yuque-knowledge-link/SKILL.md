---
name: Yuque Knowledge Link
description: "演示用 · Yuque 风格知识关联:搜索候选、收敛 Top-K、深读并生成关联报告。"
risk_level: low
version: "0.1.0"
default_ttl: 3600
allowed_tools:
  - yuque_search
  - yuque_list_docs
  - yuque_get_doc
allowed_ops:
  - relate
---

# Yuque Knowledge Link

演示用只读技能:对指定范围内的 Yuque 文档做关联分析,产出主题簇、关系边、缺口建议。

## 触发场景

<!-- Phase B 前补齐:列出 "帮我找找文档之间的关联"、"这几篇笔记有什么关系" 等自然语言触发语 -->

## 操作流程

<!-- Phase B 前补齐:按 "范围收敛 → 候选检索 → 深读抽特征 → 关系识别 → 结果呈现" 的顺序展开;参考 docs/refer/yuque-eco-system.md §知识关联 Skills 怎么写的 -->

## 错误处理

<!-- Phase B 前补齐:空候选集、超长文档、API 限流等降级策略;本技能只读,不存在写回失败分支 -->
