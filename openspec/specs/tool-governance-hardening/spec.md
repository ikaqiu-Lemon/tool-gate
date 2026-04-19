# tool-governance-hardening Specification

## Purpose
TBD - created by archiving change phase13-hardening-and-doc-sync. Update Purpose after archive.
## Requirements
### Requirement: run_skill_action MUST deny when skill meta is unresolved (D2)

The `run_skill_action` entry point SHALL treat an unresolved skill meta
(`meta is None`) as **deny-by-default**. It MUST NOT fall through to executing
the requested `op`, and MUST NOT bypass the `allowed_ops` check under any
circumstance.

#### Scenario: meta is None returns a structured deny response
- **WHEN** `run_skill_action(skill_id, op, args)` is called and the resolver
  returns `meta is None`
- **THEN** the call MUST return a structured error response indicating the skill
  meta is unavailable, MUST NOT dispatch the `op`, and MUST NOT mutate session
  state or grants.

#### Scenario: meta present still enforces allowed_ops
- **WHEN** `meta` is resolved and `op` is not in `meta.allowed_ops`
- **THEN** the call MUST return the existing `allowed_ops` denial response and
  MUST NOT dispatch the `op`.

### Requirement: PostToolUse MUST stamp last_used_at on exactly one skill (D1)

The `handle_post_tool_use` hook SHALL locate the **single** skill that owns the
just-invoked tool and update `last_used_at` on that skill only. Subsequent
skills in the iteration MUST NOT overwrite the timestamp for the same tool
invocation.

#### Scenario: matching skill is stamped exactly once
- **WHEN** a PostToolUse event arrives for a tool owned by skill A, and skills
  A and B are both loaded
- **THEN** `last_used_at` on A is updated, `last_used_at` on B is unchanged,
  and the iteration exits after the first match.

#### Scenario: no matching skill is a no-op
- **WHEN** a PostToolUse event arrives for a tool that no loaded skill owns
- **THEN** no skill's `last_used_at` is modified and no error is raised.

### Requirement: enable_skill entry points MUST be observably equivalent (D6)

Both `enable_skill` entry points (MCP and LangChain) MUST apply identical input normalisation, field mapping, Pydantic validation, error shape, and write semantics to `state.active_grants`. In particular, the LangChain wrapper `enable_skill_tool` SHALL mirror `mcp_server.enable_skill` for `scope` coercion and `granted_by` mapping.

#### Scenario: identical inputs produce identical outcomes
- **WHEN** both entry points are invoked with the same `skill_id`, `session_id`,
  and optional arguments
- **THEN** both produce the same grant record (same `allowed_ops`, TTL, and
  stored fields) and the same response shape, and both write to
  `state.active_grants` under the same key convention.

#### Scenario: identical invalid inputs produce identical errors
- **WHEN** both entry points receive the same invalid input (e.g. unknown
  `skill_id`, malformed args)
- **THEN** both return structurally equivalent error responses; neither
  silently coerces where the other rejects.

### Requirement: refresh_skills MUST perform at most one effective rescan per call (D3)

A single invocation of `refresh_skills` SHALL trigger at most one effective scan
of the skill index. The response shape SHALL remain unchanged.

#### Scenario: single call triggers one scan
- **WHEN** `refresh_skills()` is called once
- **THEN** the underlying indexer performs exactly one directory scan and
  returns the previously-documented response shape.

### Requirement: Explicit grant revoke MUST emit a grant.revoke audit event (D7)

Any code path that revokes a grant SHALL emit a structured audit event named
`grant.revoke` containing at minimum `session_id`, `skill_id`, `grant_id`, and
a `reason` discriminator (e.g. `explicit`, `ttl`, `turn`, `session`).

#### Scenario: explicit revoke emits audit event
- **WHEN** a caller explicitly revokes an active grant
- **THEN** a `grant.revoke` audit event is emitted with `reason="explicit"`
  before the grant is removed from `active_grants`.

#### Scenario: lifecycle expiry revoke emits audit event
- **WHEN** a grant is revoked by a TTL/turn/session sweep
- **THEN** a `grant.revoke` audit event is emitted with the corresponding
  `reason` discriminator.

> **Superseded by Stage B pivot (2026-04-17)**: the final implementation
> keeps TTL/turn/session expiry on the pre-existing `grant.expire` event
> (emitted by `hook_handler` after `GrantManager.cleanup_expired` marks
> the row `"expired"`), and reserves `grant.revoke` for explicit
> revocation paths only. Event boundary is documented in
> `docs/technical_design.md` §"Stage B — grant.revoke audit event (D7)"
> and pinned by
> `tests/test_grant_manager.py::TestRevoke::test_cleanup_expired_does_not_emit_grant_revoke`.
> `revoke_grant`'s `reason` parameter remains available for any future
> non-explicit revoke path; this scenario is retained for history.

### Requirement: Test coverage MUST exist for hardening branches (D4)

The test suite SHALL include cases that exercise the new branches introduced
by D2, D1, D6, D3, and D7. Existing tests MUST continue to pass (baseline:
104+ passing).

#### Scenario: meta-is-None deny branch is tested
- **WHEN** the test suite runs
- **THEN** at least one test asserts that `run_skill_action` with
  `meta is None` returns the deny response and does not dispatch.

#### Scenario: PostToolUse single-stamp is tested
- **WHEN** the test suite runs
- **THEN** at least one test asserts that `last_used_at` is stamped on
  exactly the matching skill when multiple skills are loaded.

#### Scenario: enable_skill parity is tested
- **WHEN** the test suite runs
- **THEN** at least one test exercises both `enable_skill` entry points with
  the same inputs and asserts equivalent grant and response.

#### Scenario: refresh_skills single-scan is tested
- **WHEN** the test suite runs
- **THEN** at least one test asserts that a single `refresh_skills()` call
  results in exactly one indexer scan.

#### Scenario: grant.revoke audit emission is tested
- **WHEN** the test suite runs
- **THEN** at least one test asserts that explicit revoke and at least one
  lifecycle-expiry path each emit a `grant.revoke` audit event with the
  expected `reason`.

