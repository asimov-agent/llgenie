# main-only live steps surface the real exit-2 log tail (#1714)

The main-only live-network steps (`ci-hf-live`'s liveness/registry/quant-catalog/unit-network
gates and `pipeline`'s `ci-top-tier`) fail with `make ... Error 2` whose REAL cause lives in the
target's own log tail — a dead-link `... is gone`, an `AssertionError`, a
`make: *** [...] Error 1` — but GitHub's check-run annotation showed only the generic runner
wrapper: the Node 20 deprecation warning and `##[error]Process completed with exit code 2.`,
with no trace. Measured on run `41939115306` (top-tier job `126955674736`): the log named
`AssertionError: ccore picks must be high->lower` / `tests/test_top_tier_acceptance.py:321`,
while the annotation read only `Process completed with exit code 2.` That made flake-vs-drift
undecidable from the check, forcing a manual log fetch on every red (#1250-class churn).

## The change

Each of those steps now runs its make target through `scripts/surface_failure_tail.sh`, which
tees the target's combined output to a `$RUNNER_TEMP` logfile and, on non-zero exit, emits the
ANSI-stripped tail (last 40 non-empty lines) as `::error::` workflow commands. GitHub renders
those as check-run annotations on the commit, so the annotation on a failing live step now
carries the real cause instead of the runner wrapper.

## Prove-the-guard

`tests/test_surface_failure_tail.py` pins the behaviour: a success exits 0 with no `::error::`;
a failure preserves the wrapped command's exit code AND surfaces the real tail lines (the
assertion, the `file:line`, the `make: *** [...] Error N`) as `::error::` annotations. The
failure case replays the exact measured log tail of the `ci-top-tier` red. The gate is never
weakened — the step fails exactly when the target fails (`rc` is passed through) — and no
blanket auto-retry is added, because retry would mask deterministic drift. Implements #1714.
