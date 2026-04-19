"""Top-level test session fixtures and regression guard.

Records the Stage A baseline pass count (104) recorded at the start of
``phase13-hardening-and-doc-sync`` and emits a session-finish banner
comparing the current pass count to it.  The check is a *soft*
assertion: a regression below the baseline surfaces a warning on the
report but does not fail the session, so running a subset (e.g. a
single test file) stays friction-free.
"""

from __future__ import annotations

# Pass-count at Stage A start of phase13-hardening-and-doc-sync.  Kept
# here so a regression below 104 surfaces at session finish without
# needing an external README / CI note.
PHASE13_STAGE_A_BASELINE = 104


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Emit a soft regression banner at session finish.

    Runs after pytest's own summary.  When the full suite is executed
    and the pass count is below the phase13 Stage A baseline, prints a
    highlighted warning; otherwise prints a short confirmation.  No
    ``pytest.fail`` / ``assert`` — keeps the hook informational so
    partial runs are not punished.
    """
    passed = len(terminalreporter.stats.get("passed", []))
    # Only surface the banner when the user appears to have run the
    # whole suite (heuristic: >= baseline/2).  Avoids noise for
    # deliberate subset runs.
    if passed < PHASE13_STAGE_A_BASELINE // 2:
        return
    if passed < PHASE13_STAGE_A_BASELINE:
        terminalreporter.write_sep(
            "=",
            f"regression: {passed} passed < {PHASE13_STAGE_A_BASELINE} baseline",
            red=True, bold=True,
        )
    else:
        terminalreporter.write_sep(
            "-",
            f"phase13 regression guard OK: {passed} passed >= {PHASE13_STAGE_A_BASELINE} baseline",
        )
