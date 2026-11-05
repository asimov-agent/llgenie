# ci-verdict: a post-merge straggler goes neutral, never red

## Background (measured 2026-11-05)

Run **41948125618** @ **8bc3be7d** — a `pull_request`-event CI run created at
01:22:53Z, ~24 minutes after its PR **#1737** merged (00:58:13Z, squash
`eeb3fdcc`), on a branch (`fix/top-tier-pick-size-threshold`) that the merge
then deleted. `pull_requests` on the run came back `[]`.

`ci-verdict` judged the run: no `ci-scope-decision` artifact (the branch's diff
already landed on `main`, so nothing re-selected these jobs), guard failed, the
image/linux rows skipped — and it posted a RED `verdict` row on the board. The
head could never have produced a legitimate scope decision, yet the merge gate
for the NEXT pull request read the straggler as a live red.

## The answer

A `pull_request` run whose PR is **already merged** is a straggler: it can never
publish a legitimate scope decision. Like a SUPERSEDED head, it must go
**neutral** — never `success` (its head must not read as a pass) and never red
(it must not take the board down). The tool detects it in `scripts/ci_verdict.py`
(`merged_pr_run`): via `run.pull_requests` when present, or via a
`state=all&head=<branch>` lookup when the branch was deleted and GitHub dropped
the association.

An **open** PR's run is unchanged: still judged, still red where it has no
decision — the gate is not weakened.

## Wiring

No workflow change: the decision lives in `scripts/ci_verdict.py` (the file's
own doctrine — a job-level `if:` would be invisible and untested). Tests:
`tests/test_ci_verdict.py` section 9.
