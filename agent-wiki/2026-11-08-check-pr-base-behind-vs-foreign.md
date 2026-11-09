# check-pr-base must not call a merely-behind branch's own commit foreign

2026-11-08 · issue #2138 · PR #2169

## What changed

`scripts/check_pr_base.py::_own_vs_foreign` now treats the head branch's OWN refs
as OWN even when the PR head is checked out as its **merge ref** — the shape the
`linux / unit` job checks (no PR_HEAD, so `--rev HEAD` is the synthetic 2-parent
merge commit GitHub computes on a `pull_request`). Previously the discriminator
only trusted refs that contained `rev`; the branch's own remote ref points at the
head commit (an ancestor of the merge), so it was read as a foreign signal and a
merely-behind branch (cut from an older real main, every carry its own) was
reported as carrying a FOREIGN commit. Eight open PRs redded on `linux / unit`
solely because `main` moved under them (issue #2138).

## How

- `--head-ref-name <PR_BRANCH>` names `refs/heads/<branch>` and
  `refs/remotes/origin/<branch>` as the head's own lineage;
- `--pr-number <n>` names `refs/pull/<n>/{head,merge}`;
- the `make check-pr-base` target forwards `PR_BRANCH` / `PR_NUMBER`;
- the ci.yml **guard step** and the **pipeline.yml unit job** (which already set
  `PR_BRANCH`/`PR_NUMBER` in its env) both feed them, so the head's own refs are
  never mis-reported foreign.
- `_verdict`/`check`/`render`/`main` thread the new args through; a genuine
  foreign commit (reachable from another branch's ref and not from `origin/main`)
  still reds with that commit named — the negative-control test proves it.

Verified: `tests/test_check_pr_base.py` 12 passed, `tests/test_ci_images.py` 46,
`tests/test_workflows_valid.py` 23, check-wiring / check-workflows / check-docs /
check-pr-hygiene / check-pr-closing / check-pr-authors green. Sabotage transcripts
in the PR body: a merely-behind branch at its merge ref is STALE exit 0 (and the
pre-fix run names its own server commit as "foreign", exit 1); a genuine leak
from `refs/remotes/origin/pr/other` still FAILS exit 1 naming the other lane's
commit.

The branch's own `AGENTS:`/`BASE:` stamp cites `7ef346c8` (== origin/main at open).

## Status

One atomic commit on `fix/2138-check-pr-base-behind-vs-foreign` (head `dbf4f0a7`),
opened as PR #2169 into asimov-agent/llgenie. No merge by this lane — the repo's
auto-merge lands a green, conflict-free PR.
