# Recut with content-identical graded files = re-anchor pins, and a PR's own step-if can trip the no-skip allowlist

## Recut vs re-judge (measured 2026-11-06, #1874 -> baefb1fb after #1876/#1816)

A branch recut onto live main (head `baefb1fb`) may carry base-absorption deltas in a workflow
file even when the PR's own graded artifact is unchanged. Before deciding re-judge vs re-anchor:

1. `git merge-base --is-ancestor <old-head> <new-head>` — non-ancestor means a force/recut.
2. `git diff --quiet <old-head> <new-head> -- <graded files>` — rc=0 => byte-identical.
3. Inspect the workflow-file delta line-by-line: if every differing line belongs to ANOTHER PR's
   already-merged content (e.g. #1816 umbrella-close added PR_BASE/PR_HEAD on the
   check-pr-acceptance step) and zero diff lines touch this PR's own step, the graded artifact
   is content-identical => RE-ANCHOR the AC pins to the new head, do NOT re-judge.
4. Never trust a dispatch's "graded files byte-identical" claim; measure it (`git diff --quiet`
   rc), because a workflow absorb can make it false while the semantics stay true.

### Pin the JUDGED sha, not the stub sha (measured 2026-11-06, pins on a pre-judge head)

An AC `(proven: head=<sha>)` pin can cite a sha that is NOT the sha you judged: a first writeback
ran at head A, a commit landed (A -> judged head B), the verdict was posted at B, but the pins
still read A. After a further recut to C (neither A nor B an ancestor of C), comparing A vs C makes
a graded file look DIFFERENT even though B vs C is byte-identical — the delta is the commit between
A and B, not a content change to your verdict.

- Anchor the re-anchor decision on the sha you actually reviewed (the verdict/pin body's own sha),
  not on whatever stale sha the pins happen to cite. Byte-identical graded files between the
  JUDGED sha and the true head => RE-ANCHOR to the true head; a difference between the OLD-PIN sha
  and the head is not a re-judge trigger by itself.
- Compare per-file with `git show <sha>:<path> | sha256sum` for each graded path so you can NAME
  which file differs; a whole-branch `git diff --quiet` only says "something changed".
- Refresh a stale pin with a surgical token replace (`sed s/<oldsha>/<newsha>/g` on the fetched
  body), verify counts (`0x old`, `Nx new`, ticked/proven unchanged), PATCH, then read back by id.
- The recut makes `git merge-base --is-ancestor <old> <new>` false for BOTH the pinned sha and the
  judged sha; a non-fast-forward `git fetch refs/pull/N/head:refs/remotes/live/prN` is the tell —
  refetch with `--force`, or every ancestry check silently runs against the stale pre-recut ref.
- Post a refresh note comment quoting old sha, new sha, the byte-identical evidence, and that the
  verdict id still stands — a re-anchor is attributable, never a silent pin move.

## A PR's own step-if can fail the no-skip allowlist — a real regression, route it

The no-skip guard (`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`) allows only
specific step-`if:` shapes (always(), !cancelled(), runner.os == 'Linux', matrix rows). A legit
new step condition like `if: github.event_name == 'pull_request'` (issue #845 protection) is
then REJECTED: line-681 tuple + _job_if_allowed. That failure is a REAL PR-introduced CI
regression, NOT an artifact: the PR's own ci.yml change breaks the tree's own unit test.
Verification: reproduce in the CI image at the asserted worktree HEAD
(`pytest tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped -q` -> AssertionError at
the step-if tuple), then route to the implementing lane (allowlist add or step-shape change);
ms=blocked now reflects THAT red, not base-drift. The re-anchored AC pins keep the closed
issue's gate green independently.
