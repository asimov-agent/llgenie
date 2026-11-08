# A red guard still publishes the scope decision — ci-verdict names the gate, not "NO DECISION" (#2250)

Issue: [#2250](https://github.com/asimov-agent/llgenie/issues/2250) — `ci: a guard that dies on a PR-hygiene gate erases the scope decision, so ci-verdict reds the whole head as NO DECISION`. Branch `fix/ci-scope-no-decision`, cut from `origin/main` at `334ec0cd`. PR: #2251 (`closes #2250`).

## The measurement

`ci_scope.verify()` (issue #1111) holds a finished CI run to the decision `ci.yml`'s `guard`
job publishes as the `ci-scope-decision` artifact. When the guard dies on a PR-body hygiene gate
(`check-pr-closing` ≈167, `check-pr-agents-line` ≈117, `check-pr-acceptance` ≈280 — all BEFORE
the `Publish the scope decision` ≈319 / `Upload the decision` ≈331 steps), the artifact is never
uploaded and the judge prints `NO DECISION: this run published no scope decision — no skip is
legitimate` → verdict `none` → **red for the whole ran fan-out**, masking the gate that actually
failed.

Measured at main@334ec0cd (2026-11-08): `GET …/actions/runs/<id>/artifacts` returned
`total_count: 0` on every one of the 4 affected PRs' CI runs (#2246 run 42479770472,
`check-pr-agents-line`; #2245 run 42477985847, `check-pr-closing`; #2162 run 42474939588 and
#2183 run 42475647633, `check-pr-acceptance`), so ci-verdict redded all of them as
"NO DECISION" rather than naming the gate.

## The fix (this change's pull request)

Mark the two decision steps `if: always()` in `ci.yml`'s `guard` job (`Publish the scope
decision` and `Upload the decision`). A failing sibling PR-hygiene gate can no longer erase the
decision: `Upload the decision` keeps `if-no-files-found: error`, so a run that genuinely cannot
produce a decision still fails hard. With a decision present, `ci_scope.verify()` reports
`guard FAILED (check-pr-X)` (failure=1, skips no_verdict) — the actual actionable gate — instead
of "NO DECISION for everything".

Proven live: run 42483418440's red guard still published the `ci-scope-decision` artifact
(`count: 1`), and the pin `tests/test_ci_scope_decision_unconditional.py` is green with the two
`if: always()` lines and red (AssertionError) when they are removed (sabotage loop, both ways).
