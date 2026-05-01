## ADDED Requirements

### Requirement: Runtime state and persisted state are semantically distinct

The system SHALL maintain a semantic separation between **runtime state** (values a turn computes and consumes while it executes) and **persisted state** (the minimal durable record required to recover, continue, or audit a session). A turn MUST NOT treat a previous turn's runtime-derived value as authoritative input for its own governance decisions, and the persisted record MUST NOT be consumed directly as runtime state without an explicit per-turn reconstruction.

#### Scenario: A derived value from an earlier turn is not reused as authoritative input

- **WHEN** a turn produces a derived value — such as the set of tools currently visible to the model — and a subsequent turn begins on the same session
- **THEN** the new turn SHALL recompute that derived value from current authoritative sources and SHALL NOT feed the earlier turn's result into its own rewrite or gate-check decisions

#### Scenario: Persisted record is not handed directly to per-turn logic

- **WHEN** a hook or meta-tool entry loads the persisted record for a session
- **THEN** it SHALL first construct a fresh runtime view from (persisted record, current skill index, current policy, current clock) and only then invoke rewrite or gate-check logic against that view

### Requirement: Persisted state contains only recovery, continuity, and audit fields

The persisted session record SHALL contain only fields needed to (a) identify the session, (b) restore cross-turn continuity of currently authorized skills and their grant state, or (c) anchor audit records. It MUST NOT persist fields whose sole purpose is to serve as a single turn's rewrite input or display cache; such fields are runtime-only and SHALL be recomputed on demand at turn start.

#### Scenario: Persisted record excludes pure per-turn derivations

- **WHEN** a session is persisted after a turn completes
- **THEN** the persisted record SHALL include session identity, the set of enabled skills with their grant state, and the timestamps required for audit; it SHALL NOT persist a field whose only role is to cache the current turn's active tool set or composed context

#### Scenario: Audit replay works from persisted state alone

- **WHEN** an audit event is reconstructed from the audit log and the persisted record
- **THEN** the reconstruction SHALL succeed without consulting any runtime-only value, because every field the audit event depends on is either in the persisted record or in the event's own payload

### Requirement: Runtime state is reconstructed safely from persisted state plus current context

At the start of every turn the system SHALL build a complete runtime view from (a) the loaded persisted record, (b) the current skill index and policy, and (c) the current clock. The reconstruction SHALL be deterministic given the same inputs, and MUST complete before any rewrite, prompt composition, or gate-check observes the new turn's state.

#### Scenario: Every turn begins with a fresh runtime view

- **WHEN** a hook or meta-tool entry is invoked for a turn
- **THEN** the system SHALL load persisted state, expire grants whose TTL has passed, and derive the turn's active tool set and display context from the loaded state plus the live skill index and policy — before any other governance logic runs

#### Scenario: Identical inputs yield equivalent runtime views

- **WHEN** the same persisted record is reconstructed twice under identical skill-index, policy, and clock inputs
- **THEN** the two resulting runtime views SHALL be equivalent for every governance decision they drive — the same tools allowed, the same skills treated as enabled, the same authorization status reported

### Requirement: System degrades safely when persisted state is missing, stale, or incomplete

When the persisted record is absent, carries fields from an older code version, or references skills or grants that no longer resolve under the current skill index or policy, the system SHALL degrade to a safe runtime view that excludes unresolved items but continues to operate. Under no such condition SHALL the system crash, elevate authorization beyond what the persisted record still justifies, or use a stale field as if it were current-turn authoritative input.

#### Scenario: No persisted record exists for the session

- **WHEN** a turn begins and no persisted record is found for the session id
- **THEN** the system SHALL construct a fresh empty runtime view — no skills loaded, no authorized tools beyond the always-available meta-tools — and proceed without error

#### Scenario: Persisted record references an unknown skill

- **WHEN** the persisted record lists a skill that no longer exists in the current skill index
- **THEN** the system SHALL exclude that skill from the runtime view, leave the persisted entry untouched for audit purposes, and SHALL NOT grant any tools on behalf of the unknown skill

#### Scenario: Persisted record carries fields from an older code version

- **WHEN** the loaded persisted record includes fields that the current code treats as runtime-only
- **THEN** the system SHALL ignore those legacy fields when deriving the runtime view, compute the runtime view from current authoritative sources instead, and retain the legacy fields on disk only if they are still needed for audit or continuity
