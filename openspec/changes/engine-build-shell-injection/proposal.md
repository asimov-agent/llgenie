# Proposal: engine-build-shell-injection

## Why

`make security-verdict EVENT=schedule` on `main` `2f6574ea8` blocks on exactly one
finding after #2608/#2610/#2611 landed: semgrep
`github-actions.security.run-shell-injection` (high) at
`.github/workflows/engine-build.yml:149` — the #2578 Dispatch provenance step assigns
the dispatch input with `producer="${{ inputs.producer_run }}"`. GitHub expands the
expression into the shell text BEFORE the shell runs, so a `workflow_dispatch` value
containing `"` or `$( )` executes inside the double quotes. Filed by the sanctioned
producer as issue #2622.

## What Changes

- The Dispatch provenance step passes `inputs.producer_run` and
  `github.triggering_actor` through its `env:` block; the shell reads `$PRODUCER_RUN`
  / `$TRIGGERING_ACTOR` only.
- The existing lock test `test_liveness_dispatches_name_their_producer_run` is
  extended: the provenance step's `run:` body must contain no GitHub expression, and
  both env bindings must exist (issue #2622).
- One #330 pitfall handled on the way: the step comment must not quote an empty
  `${{ }}` token — check-workflows parses every expression in the file's raw text.

## Impact

- Affected: `.github/workflows/engine-build.yml`, `tests/test_check_engine_pins_published.py`
- Affected specs: `engine-build-provenance` (MODIFIED — env-passed values)
- Daily security-scan verdict: the last blocking finding clears once this lands.
