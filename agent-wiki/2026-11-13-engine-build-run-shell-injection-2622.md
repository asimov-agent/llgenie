# 2026-11-13 — engine-build run-shell-injection (#2622)

## What was verified

- `semgrep` `yaml.github-actions.security.run-shell-injection.run-shell-injection`
  flagged `.github/workflows/engine-build.yml:148` (the guard job's "Dispatch provenance"
  step, introduced by #2589) at HIGH: the step embedded `${{ inputs.producer_run }}` and
  `${{ github.triggering_actor }}` directly in its `run:` block. `inputs` is in the rule's
  pattern set (`- pattern: ${{ ... inputs ... }}`) and `github.*` context data is treated
  as untrusted — the exact shape the rule exists to forbid.
- Fix mirrors the sibling guard step's own pattern and the rule's prescribed remediation:
  the values are moved into an `env:` block (`PRODUCER_RUN`, `TRIGGERING_ACTOR`) and the
  `run:` text reads only the quoted shell vars `"$PRODUCER_RUN"` / `"$TRIGGERING_ACTOR"`.
  The visible behaviour is unchanged: `dispatched_by_run=<id>` (or the
  `dispatched_by_run=none-recorded actor=<actor>` fallback for a human/PR-lane dispatch)
  is still echoed to the log and `$GITHUB_STEP_SUMMARY`.
- No `inputs`, `github.event.*`, `github.ref`/`base_ref`/`head_ref`/`ref_name`, or
  `github.triggering_actor` expression remains in ANY `run:` block of the file (the only
  remaining raw `${{ }}` in run text are `matrix.engine`/`matrix.variant`/`github.sha`,
  none of which are in the rule's pattern set).

## Decisions

- The provenance step keeps `inputs.producer_run` and `GITHUB_STEP_SUMMARY` in its text so
  `tests/test_check_engine_pins_published.py::test_liveness_dispatches_name_their_producer_run`
  (the text lock for the whole #2578 feature) keeps passing — verified 1 passed.
- The docker-login step's `github.actor` / `secrets.GITHUB_TOKEN` are untouched: they are
  outside the rule's pattern set and were never part of this finding.

## Current status

- `make check-workflows` rc=0 ([workflows] OK). `tests/test_check_engine_pins_published.py`
  + `test_workflow_guards.py` + `test_workflow_actor_gates.py`: 62 passed.
- Live semgrep re-scan requires the docker daemon (unavailable in this container); the
  static rule-contract check (`no inputs/github.* in any run: block`) is the local proof.
  The pipeline's next scheduled scan is the authoritative clearing run.
- Implements issue #2622.
