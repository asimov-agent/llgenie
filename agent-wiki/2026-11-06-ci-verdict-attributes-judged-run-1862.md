# 2026-11-06 ci-verdict attributes the judged run, not its wrapper (issue #1862)

The `ci-verdict` check-run is posted by a `workflow_run` workflow, whose own head
is always the repository's default branch. A red verdict for an open pull
request's CI run therefore appeared, to a board reader listing runs by
`head_sha`, as a red at the merged-main tip — the misattribution behind #1862's
"verdict reds at merge tips" framing. Measured (2026-11-06): every cited red
verdict run judged a `pull_request` CI run of an open PR whose `guard` genuinely
failed, and the current main tip carried exactly one `ci-verdict` check-run =
`success` — there was no false-red to weaken, and `verify()`'s no-decision
branch (AC2) is untouched.

The fix names the run the verdict JUDGED, not the wrapper that ran it:
`scripts/ci_verdict.py::verdict_lines()` now appends `event=<event>` and, when
the judged run carries them, `pr=<n>+<m>` and `branch=<head_branch>` to the
posted check-run summary header. A reader can now tell a PR-1850 verdict red
from a merge-tip red immediately — the "post-merge verification must not need
manual standing-pattern characterization" benefit of #1862 — without any change
to what the verdict decides.

Verified: the new `test_the_verdict_header_attributes_the_judged_run_event_and_pr_not_the_wrapper`
reds on the old header (which lacked the attribution) and is green on this tree;
123 tests pass across `test_ci_verdict`/`test_ci_scope`/`test_ci_requeue`/`test_ci_images`.
