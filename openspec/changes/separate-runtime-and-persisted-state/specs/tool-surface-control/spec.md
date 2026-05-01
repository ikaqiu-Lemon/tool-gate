## ADDED Requirements

### Requirement: Prompt and tool rewrite consume runtime state, not persisted snapshot

Per-turn prompt composition and tool-set rewriting SHALL operate on a runtime view that was freshly derived for the current turn from (the loaded persisted record, the current skill index, the current policy, the current clock). These operations MUST NOT read persisted fields directly as their governance input, and MUST NOT trust any field that a previous turn's rewrite or compose step itself produced.

#### Scenario: Rewrite input is the current turn's runtime view

- **WHEN** the tool-set rewrite runs at the start of a turn
- **THEN** its inputs SHALL be the runtime view built for that turn from the freshly loaded persisted record plus the live skill index and policy — not a derived field read back from the persisted record

#### Scenario: Prompt composition ignores stale prior-turn derivations

- **WHEN** the prompt composer assembles the context injected for a turn
- **THEN** it SHALL consume only the turn's runtime view; if the persisted record happens to carry a stale active-tools or catalog field written by an earlier turn, the composer SHALL ignore it and use the freshly derived values

#### Scenario: Policy or index changes between turns take effect on the next turn

- **WHEN** the blocked-tools policy or the skill index changes between two consecutive turns on the same session
- **THEN** the later turn's runtime view SHALL reflect the new policy and index, and the rewrite and composed context for that turn SHALL NOT carry over any value derived under the earlier policy or index
