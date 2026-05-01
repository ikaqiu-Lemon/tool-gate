# delivery-demo-harness Specification Delta

## ADDED Requirements

### Requirement: Legacy Demo Changes MUST NOT Be Canonical Guidance

Legacy delivery-demo changes (archived `add-delivery-demo-workspaces` and active `harden-demo-workspace-onboarding`) MUST NOT be treated as canonical implementation guidance for demo workspaces. The canonical source of truth for demo workspace structure, behavior, and onboarding SHALL be `openspec/specs/delivery-demo-harness/` and the current `examples/` directory content.

#### Scenario: Reader discovers demo workspaces

- **WHEN** a new reader or agent explores the repository to understand demo workspaces
- **THEN** they SHALL be directed to `examples/README.md` and `examples/QUICKSTART.md` as the primary entry points
- **AND** they SHALL NOT be directed to `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` as default guidance

#### Scenario: Model searches for demo implementation guidance

- **WHEN** an AI model searches for "how to run demo workspaces" or "demo workspace structure"
- **THEN** the model SHALL find guidance in `examples/QUICKSTART.md` and `openspec/specs/delivery-demo-harness/spec.md`
- **AND** the model SHALL NOT treat legacy change artifacts as the primary source of truth

#### Scenario: Legacy changes referenced as historical context only

- **WHEN** legacy demo changes are referenced in documentation or commit messages
- **THEN** they MUST be explicitly labeled as "historical context only", "not canonical", or "superseded by current examples/"
- **AND** they SHALL NOT be presented as current implementation instructions

### Requirement: Repository Navigation MUST Point To Canonical Demo Path

Current repository navigation (README, QUICKSTART, agent guidance documents) MUST point readers and agents to `examples/` directory and `openspec/specs/delivery-demo-harness/` as the canonical demo source of truth. Navigation MUST NOT default to OpenSpec change artifacts for demo discovery.

#### Scenario: Root README demo navigation

- **WHEN** a reader opens the root `README.md` or `README_CN.md`
- **THEN** any demo-related links SHALL point to `examples/README.md` or `examples/QUICKSTART.md`
- **AND** no links SHALL point to `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` as primary demo entry points

#### Scenario: Agent guidance demo references

- **WHEN** agent guidance documents (`AGENTS.md`, `CLAUDE.md`, or similar) reference demo workspaces
- **THEN** they SHALL direct agents to `examples/` directory and `openspec/specs/delivery-demo-harness/`
- **AND** they SHALL NOT direct agents to legacy change artifacts as default demo guidance

#### Scenario: Examples directory as primary demo entry

- **WHEN** documentation describes how to explore demo workspaces
- **THEN** it SHALL state that `examples/README.md` and `examples/QUICKSTART.md` are the primary entry points
- **AND** it SHALL state that `openspec/specs/delivery-demo-harness/` defines the canonical requirements

### Requirement: Safe Deletion SHALL NOT Remove Current Requirements

Deleting legacy demo change directories SHALL NOT remove still-needed current requirements from main specs without replacement. Before deletion, all necessary demo workspace requirements MUST already exist in `openspec/specs/delivery-demo-harness/spec.md` or be explicitly documented as no longer needed.

#### Scenario: Pre-deletion requirement audit

- **WHEN** legacy demo changes are scheduled for deletion
- **THEN** a deletion impact report MUST be generated that lists all requirements from the legacy changes
- **AND** the report MUST confirm that each still-needed requirement already exists in the main spec or has been explicitly deprecated

#### Scenario: Main spec completeness after deletion

- **WHEN** legacy demo change directories are deleted
- **THEN** `openspec/specs/delivery-demo-harness/spec.md` MUST contain all current demo workspace requirements
- **AND** `openspec validate --all` MUST pass without errors

#### Scenario: Historical requirements explicitly marked

- **WHEN** a requirement from a legacy change is no longer needed
- **THEN** the deletion impact report MUST explicitly state why it is no longer needed
- **AND** the requirement SHALL NOT be silently dropped without documentation

### Requirement: Active Legacy Demo Changes MUST Be Removed From Active Set

Once cleanup is complete, active legacy demo changes (specifically `harden-demo-workspace-onboarding`) MUST be removed from the active change set. Future workflow SHALL NOT continue to rely on `harden-demo-workspace-onboarding` as an active change.

#### Scenario: OpenSpec list excludes removed changes

- **WHEN** `openspec list` is executed after cleanup completion
- **THEN** the output SHALL NOT include `harden-demo-workspace-onboarding`
- **AND** the output SHALL NOT include any other legacy demo changes marked for removal

#### Scenario: Active change directory removed

- **WHEN** cleanup Stage D (deletion) is complete
- **THEN** the directory `openspec/changes/harden-demo-workspace-onboarding/` SHALL NOT exist
- **AND** the directory `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/` SHALL NOT exist

#### Scenario: Future changes do not depend on removed changes

- **WHEN** new changes are created after cleanup completion
- **THEN** they SHALL NOT reference `harden-demo-workspace-onboarding` or `add-delivery-demo-workspaces` as dependencies
- **AND** they SHALL reference `openspec/specs/delivery-demo-harness/` for demo workspace requirements

## MODIFIED Requirements

### Requirement: Demo Workspace Discovery Flow SHALL Start From Examples Directory

Demo workspace discovery flow SHALL start from `examples/README.md` and `examples/QUICKSTART.md`, not from OpenSpec change artifacts. The primary onboarding path for new users and agents SHALL be the examples directory, with `openspec/specs/delivery-demo-harness/` serving as the canonical requirements reference.

#### Scenario: New user discovers demo workspaces

- **WHEN** a new user wants to explore demo workspaces
- **THEN** they SHALL be directed to `examples/README.md` as the primary entry point
- **AND** `examples/README.md` SHALL link to `examples/QUICKSTART.md` for step-by-step onboarding
- **AND** neither document SHALL direct users to OpenSpec change artifacts as the primary discovery path

#### Scenario: Agent explores demo capabilities

- **WHEN** an AI agent is asked to demonstrate tool-governance capabilities
- **THEN** the agent SHALL consult `examples/QUICKSTART.md` for runnable demo instructions
- **AND** the agent SHALL consult `openspec/specs/delivery-demo-harness/` for canonical requirements
- **AND** the agent SHALL NOT default to reading `openspec/changes/harden-demo-workspace-onboarding/` or `openspec/changes/archive/2026-04-21-add-delivery-demo-workspaces/`

#### Scenario: Documentation cross-references point to examples

- **WHEN** any project documentation references demo workspaces
- **THEN** cross-references SHALL point to `examples/` directory or `openspec/specs/delivery-demo-harness/`
- **AND** cross-references SHALL NOT point to legacy change artifacts unless explicitly labeled as historical context
