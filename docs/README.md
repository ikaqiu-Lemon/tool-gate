# Tool-Gate Documentation

This directory contains documentation for the tool-gate project.

## Available Documents

### [session_logging_prompt.md](./session_logging_prompt.md)
**Session Logging Implementation Guide for Tool-Gate**

A comprehensive prompt tailored specifically for the tool-gate project that guides the implementation of structured session logging and audit trail generation.

**Key Features**:
- Designed for the tool-governance middleware architecture (not a standalone agent)
- Leverages existing SQLite audit_log infrastructure
- Generates JSONL event streams, Markdown audit reports, and JSON metrics
- Minimal invasive approach - no changes to core Hook or MCP logic
- Includes state snapshots, funnel analysis, and governance decision tracking

**Sections**:
1. Core Understanding - Architecture overview
2. Implementation Plan - 15 detailed sections covering:
   - Session logger module design
   - Log file structure and naming
   - Session metadata recording
   - Skill exposure and authorization tracking
   - Tool call governance and error classification
   - State and cache management
   - Langfuse integration
   - Audit summary generation
   - Metrics aggregation
   - Implementation requirements
   - Verification procedures
3. Appendix - Differences from generic agent logging prompts

**Target Audience**: Developers implementing observability features for the tool-governance system.

**Document Stats**: 819 lines, ~50KB

---

## Document Organization

Documents are organized by topic:
- `session_logging_prompt.md` - Observability and audit logging

More documentation will be added as the project evolves.

