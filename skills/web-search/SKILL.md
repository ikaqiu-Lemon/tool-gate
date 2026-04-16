---
name: Web Search
description: "Search the web and fetch page content for research."
risk_level: low
version: "1.0.0"
default_ttl: 3600
allowed_tools:
  - WebSearch
  - WebFetch
allowed_ops:
  - search
  - fetch
---

# Web Search

Web research capabilities.

## Workflow

1. Use `WebSearch` to find relevant pages
2. Use `WebFetch` to retrieve and read page content

## Rules

- Only use for research purposes
- Verify information from multiple sources when possible
