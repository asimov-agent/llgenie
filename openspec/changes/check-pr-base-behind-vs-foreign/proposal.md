# check-pr-base-behind-vs-foreign — proposal

Issue: [#2138](https://github.com/asimov-agent/llgenie/issues/2138)

## Why

`check-pr-base` reported a branch that is merely BEHIND `origin/main` (main
moved under it after the branch was cut) as carrying a FOREIGN commit — and
the "foreign commit" it named was the branch's OWN commit. Measured on
2026-11-08 at eight open PRs red on `linux / unit` solely because `main`
advanced under them; the failing log line at #2069 head `9c3cac06` and #2127
head `9581c3ee` read `[check-pr-base] FAILED: \`HEAD\` is NOT cut from
\`origin/main\` — its merge-base with ...`. "Behind" and "carries another PR's
commits" are different facts and must be judged differently; calling a branch's
own commit foreign is a false diagnosis that blocks a rebase-free PR.

## What Changes

- In `scripts/check_pr_base.py::_own_vs_foreign`, the head branch's OWN refs
  (`refs/heads/<branch>` and `refs/remotes/origin/<branch>`, from a new
  `--head-ref-name <PR_BRANCH>`) and the PR's synthetic refs
  (`refs/pull/<n>/{head,merge}`, from a new `--pr-number <n>`) are OWN lineage,
  not foreign signals — even in the `linux / unit` shape where GitHub checks
  out the PR head as its **merge ref** so the branch's own remote ref does not
  contain `rev`.
- A branch whose merge-base is an older real `main` tip and whose `base..rev`
  carries nothing reachable from another ref is judged STALE (green, distinct
  message), never FOREIGN.
- A branch that genuinely carries another branch's commit (reachable from a
  non-`origin/main` ref, e.g. `refs/remotes/origin/<other>`) still FAILS with
  that commit named.
- `--head-ref-name`/`--pr-number` are threaded through `_verdict`/`check`/
  `render`/`main`; `make check-pr-base` forwards `PR_BRANCH`/`PR_NUMBER`; the
  ci.yml guard step sets them for both call sites.

## Out of scope

- No rebase or push of any open PR; no other gate; no new workflow.
- The `check-pr-acceptance` red on #2183 is issue #2138's unticked criteria and
  is owned by the review lane, not this change.
