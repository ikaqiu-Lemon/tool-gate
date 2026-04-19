---
name: Mock Malformed
description: "Intentionally broken frontmatter — must be skipped by SkillIndexer.
risk_level: low
allowed_tools:
  - [this list is intentionally malformed
    YAML: unclosed_bracket
---

# Mock Malformed

The YAML frontmatter above is intentionally invalid (unterminated string on
the description line, malformed list entry). `SkillIndexer._index_one`
must catch the `yaml.YAMLError`, log a warning, and skip the file without
aborting the scan of valid siblings.
