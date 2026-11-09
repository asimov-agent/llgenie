# ci-images step/job `if:` allowlist — the guard's own unit red

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` (around lines 618-695) enforces an
EXACT allowlist of `if:` conditions in `ci.yml` / `pipeline.yml`:

- **Job-level** `if:`s are checked by `_job_if_allowed()` against `_PUSH_WAIT` (push-scoped waits)
  plus a few exact strings (`matrix.engine != 'none'`, push + `needs.engine-image.result=='success'`).
- **Step-level** `if:`s must be one of a fixed tuple: `${{ !cancelled() }}`, `always()`,
  `runner.os == 'Linux'`, `runner.os == 'macOS'`, the matrix-row conditions, and
  `github.event_name == 'pull_request'` (added for issue #1867).

## The trap

A change that ADDS a new `if:` shape to a step/job silently reds `linux / unit`, because the unit
test asserts the exact string is in its tuple. First real instance: gating the `check-pr-base` step
to `if: github.event_name == 'pull_request'` (issue #1867, closes #845 phantom-red on push-to-main).
The gate was correct; the guard's own test rejected it until the tuple gained that exact string with
a comment naming the issue.

## Rule

This is the standing *"a shape change has a spelling; find who asserted it"* rule in its ci-images
form. Before pushing ANY workflow `if:`/job-name/step-shape change:

1. `grep -n "test_no_ci_step_or_job_is_skipped\|_job_if_allowed\|_PUSH_WAIT" tests/test_ci_images.py`.
2. If you added a genuinely new, intended `if:` shape, extend the allowlist tuple (or `_PUSH_WAIT`)
   with the exact string AND a comment naming the issue that justifies it — never leave the step
   un-gated just to satisfy the test, and never delete the test.
3. Prove with the WHOLE file in the container: `pytest tests/test_ci_images.py` → all pass (34 at
   #1867 head), not just the single test.

## Note on stale heads

The rebase lane may report this red against an intermediate pre-fix head (e.g. `baefb1fb` before
`97abfafb`). Always re-measure the LIVE PR head (`gh api pulls/<n>` → head.sha) and run the whole
file there before concluding a fix is owed — a landed allowlist commit makes the finding moot.
