## ADDED Requirements

### Requirement: Installation Origin Anchored at Repository Root

The onboarding flow MUST present project installation (`pip install -e ".[dev]"`) as a step that runs from the **repository root**, before any instruction that enters a workspace directory. The flow SHALL provide a copy-paste-safe form that works regardless of the reader's current shell directory, and MUST surface the "ran pip from workspace cwd" failure mode explicitly so a reader who hits it can self-diagnose.

#### Scenario: Install step precedes workspace entry in reading order

- **WHEN** a reader reads the shared onboarding entry document top-to-bottom
- **THEN** the first `pip install` instruction appears before the first `cd examples/` instruction
- **AND** the `pip install` instruction either uses an absolute path to the repository root or is introduced by a `cd` to the repository root that is visually paired with it in the same code block

#### Scenario: Workspace README does not re-issue the install command

- **WHEN** a reader opens any `examples/0X-*/README.md`
- **THEN** the workspace README does not contain a standalone `pip install -e` code block
- **AND** the workspace README cross-references the shared onboarding entry document for installation

#### Scenario: The workspace-cwd install error is cataloged

- **WHEN** the onboarding troubleshooting catalog is consulted with the observable symptom `does not appear to be a Python project: neither 'setup.py' nor 'pyproject.toml' found`
- **THEN** the catalog returns the root cause (install command executed inside a workspace directory instead of the repository root) and a one-line fix

---

### Requirement: Runtime Composition Explained Once, in One Place

The onboarding flow SHALL contain exactly one authoritative explanation of how the running demo session is composed at startup. That explanation MUST name and relate (a) the plugin manifest, (b) the hooks configuration, (c) the workspace MCP server registrations, and (d) the `GOVERNANCE_*` environment variables. Workspace READMEs MUST NOT duplicate this explanation; they MAY only reference it.

#### Scenario: Shared entry document contains the wiring map

- **WHEN** a reader opens the shared onboarding entry document
- **THEN** a single section presents a wiring map that names the plugin manifest, hooks configuration, MCP registrations, and `GOVERNANCE_*` environment variables
- **AND** each named element is accompanied by a one-sentence statement of what it contributes to the running session

#### Scenario: Workspace READMEs do not duplicate the wiring map

- **WHEN** any `examples/0X-*/README.md` is inspected
- **THEN** the workspace README does not contain its own wiring diagram or its own enumeration of the four elements above
- **AND** it cross-references the shared onboarding entry document for those concepts

#### Scenario: A reader can trace the startup command to the four elements

- **GIVEN** a reader has read only the shared onboarding entry document
- **WHEN** the reader is shown the startup command `claude --plugin-dir ../../ --mcp-config ./.mcp.json`
- **THEN** the reader can identify, for each of the four elements, which part of the command activates it

---

### Requirement: Credential-Free Happy Path Is the First-Run Default

The onboarding flow MUST provide a runnable happy path that produces observable governance decisions **without requiring** Anthropic API access, network access, or a Claude Code CLI installation. This credential-free path SHALL be presented before any path that requires an API key. Any path that does require an API key MUST be clearly labeled as optional / advanced relative to the credential-free path.

#### Scenario: Credential-free path is presented first

- **WHEN** a reader reads the shared onboarding entry document's "how to run" section top-to-bottom
- **THEN** the credential-free path (subprocess replay that pipes a JSON event to the governance hook handler) is presented before the Claude Code CLI path

#### Scenario: Walking the credential-free path yields a visible decision

- **WHEN** a reader follows the credential-free path exactly as written, without setting any `ANTHROPIC_*` or similar API key environment variable
- **THEN** the path produces an observable permission decision (`allow`, `deny`, or `ask`) visible in stdout
- **AND** the path does not make any outbound network call to a model provider

#### Scenario: Claude Code CLI path is labeled as requiring credentials

- **WHEN** the Claude Code CLI path is introduced in the shared onboarding entry document
- **THEN** the document states that this path requires an Anthropic API key and is optional relative to the credential-free path

---

### Requirement: Per-Workspace Verify and Reset Recipes

Each demo workspace MUST document (a) how to verify the demo ran as intended by inspecting the persisted audit trail, and (b) how to reset demo state so the next run starts clean. Both recipes SHALL be expressed as concrete commands the reader can copy and run; verify output MUST be comparable against the workspace README's existing expected audit rows.

#### Scenario: Verify recipe exists and is concrete

- **WHEN** a reader opens any `examples/0X-*/README.md`
- **THEN** the workspace README contains a verify section with a concrete command that reads from the audit table produced at the workspace's `GOVERNANCE_DATA_DIR`
- **AND** that section cross-references the workspace's existing expected-audit-row listing

#### Scenario: Reset recipe exists and is safe

- **WHEN** a reader opens any `examples/0X-*/README.md`
- **THEN** the workspace README contains a reset section with a single command that removes only the workspace's own demo state directory
- **AND** the reset command does not touch files outside that workspace

#### Scenario: Reset then rerun is idempotent

- **GIVEN** a reader runs the full demo once, then runs the reset recipe, then runs the demo again
- **WHEN** the reader then runs the verify recipe
- **THEN** the audit rows observed after the second run match the workspace README's expected-audit-row listing
- **AND** the output is not polluted by rows from the first run

---

### Requirement: Single Troubleshooting Catalog Indexed by Symptom

The onboarding flow MUST maintain exactly one troubleshooting catalog, indexed by observable reader-facing symptoms rather than by internal cause. Workspace READMEs MAY add entries specific to their own flow but MUST NOT maintain a separate catalog for shared symptoms. The catalog MUST cover, at minimum, the recurring startup failure classes listed below.

#### Scenario: Shared catalog exists and covers minimum failure classes

- **WHEN** the onboarding troubleshooting catalog is opened
- **THEN** it contains entries covering at least these symptom classes:
  (i) `pip install` executed from a workspace directory,
  (ii) `tg-hook` or `tg-mcp` not found on `PATH`,
  (iii) `claude` CLI not found on `PATH`,
  (iv) `.mcp.json` relative path fails to resolve because the session was not launched from the workspace root,
  (v) one or more `GOVERNANCE_*` environment variables unset,
  (vi) a workspace mock MCP exits non-zero during startup self-check due to schema drift,
  (vii) demo appears to hang waiting for TTL expiry in the lifecycle workspace,
  (viii) a newly added skill is not visible until the skill index is refreshed

#### Scenario: Each catalog entry is actionable

- **WHEN** the reader looks up any entry in the troubleshooting catalog
- **THEN** the entry provides, at minimum: the observable symptom, the root cause, a verification command the reader can run to confirm the cause, and a fix action

#### Scenario: Workspace READMEs reference the shared catalog

- **WHEN** any `examples/0X-*/README.md` references a symptom covered by the shared catalog
- **THEN** the workspace README points to the shared catalog rather than restating the entry
- **AND** a workspace-specific troubleshooting section, if present, contains only symptoms unique to that workspace's flow
