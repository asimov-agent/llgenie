# Adding a job to `ci.yml`, and verifying a bot/CI change locally

## A new job-level `if:` reds the skip guard

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` is a whitelist: every job-level `if:` must be
"a wait for its `needs:`" or "skip the `none` placeholder row", and every step-level `if:` must be one of
a handful of literals (`${{ !cancelled() }}`, `always()`, `runner.os == …`, `matrix.engine != 'none'`).

A legitimately scenario-scoped job — anything that must not run on a push, e.g. a merge or a publish gate
— needs an entry in `_job_if_allowed` **carrying its reason as a comment**. Extend the whitelist; never
delete the assertion, and never stretch an existing branch until the new condition happens to match. The
guard exists so OS/matrix decisions stay inside `make` instead of multiplying in YAML.

## "Green" for a dependent job: every need SUCCEEDED

`always() && !failure() && !cancelled()` is not "green": a SKIPPED job (collapsed matrix, a job killed by
a concurrency group, a push-only job on a PR run) satisfies all three. A gate written that way acts on a
run whose stage never executed.

- Require `needs.<job>.result == 'success'` for every job the gate actually depends on, listed explicitly.
- Keep `always()` in the expression so the byte-level `!failure()`/`!cancelled()` guards still apply, and
  keep a push-only job out of `needs:` rather than letting its skip drag the gate.
- Assert each `needs.<job>.result == 'success'` in the workflow test, so a later edit that drops one reds
  `make test-unit` instead of silently widening the gate.

## The merge-shaped job (what a green PR gate needs)

When CI itself lands a PR: `--squash --delete-branch --match-head-commit <sha>` (pin the commit the run
validated), merge with the OWNER PAT rather than the job token (a merge made with the job token starts no
workflows, so the post-merge run on `main` never happens), and read the merge state from ONE
`gh pr view --json state,isDraft,mergeable,mergeStateStatus,headRefOid,labels`. `mergeStateStatus: CLEAN`
is the whole "no conflicts, not stale, not blocked" rule; `DIRTY`/`BEHIND`/`BLOCKED` each name a reason a
human must handle, so they print and exit 0 — a deferral is never a failed run. Honour a `do-not-merge`
label as the reviewer's hold, and prove the body's `closes #n` bound afterwards (see
`references/fake-gh-fixtures.md` for how to test the decision against a real fake `gh`).

## Running the suites locally

- **One `make test-unit` at a time.** The suite carries live-Hub checks (README trend links, the
  vendored-registry link check, a real GGUF download). Two concurrent runs trip the Hub rate window and
  those files go red with `HTTP Error 429: Too Many Requests` while the tree is fine — the reds are the
  rate limit, not your diff. Run them sequentially; a run that stalls for minutes inside the download is
  the same class (the pytest `faulthandler` dump is not a verdict).
- Chain suites in one background script (`run <worktree> <log>`) rather than launching them in parallel,
  and read `EXIT=` plus the last summary line, not the progress dots.
- After a rebase onto a moved `main`, re-run the affected test file before pushing: a union resolution can
  duplicate a stanza or keep a stale literal, and CI is an expensive way to find that out.

## Dispatching a bot and holding a claim

- **Labelling an issue `agent:implement` / `agent:ready` IS a dispatch.** The issue-bot triggers on
  `issues: labeled`, so labelling and then dispatching by hand starts two runs; the second queues behind
  the first (`cancel-in-progress: false`) and can implement the same issue again. Either label it or
  dispatch it — not both. Remove the label if you are implementing it yourself.
- **A cancelled or wedged run keeps its claim until the claim TTL expires.** A plain re-dispatch then
  picks the NEXT free issue; `gh workflow run … -f issue_number=<n>` pins the work you meant.
- `dispatch --dry` is the deterministic oracle for "who would be picked": run it locally before
  dispatching, instead of guessing from labels and timestamps.

## Makefile: `REPO` is the worktree path

The Makefile defines `REPO := $(CURDIR)`, so a target that needs an `owner/repo` slug cannot default it:
`$(if $(REPO),$(REPO),asimov-agent/llgenie)` always yields the path. Require it explicitly
(`@test -n "$(REPO)" || { echo "Usage: … REPO=<owner/repo>"; exit 1; }`) and pass `"$(REPO)"`, so a local
run fails with usage instead of handing `gh` a directory path.
