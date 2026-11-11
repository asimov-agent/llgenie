# Stale check-run ids: only the latest run per (name, commit) is live

## Rule

A check-run id you quoted from an earlier read can be **superseded** — GitHub surfaces only the latest
check-run per (name, commit) pair. A `failure` at 03:40 does not mean the gate is red if a rerun at 03:54
reported `success` for the same name on the same commit.

Before calling any cited check-run a live red:

```bash
gh api repos/<owner>/<repo>/commits/<sha>/check-runs \
  --jq '.check_runs[]|select(.name=="ci-verdict")|{id,status,conclusion,at:.completed_at}'
```

One entry = the live pair. If its `conclusion` is `success`, the older failing id is history, not a defect.

## Corollaries

- **Cite the id you just read, not the id from a chat message or an earlier turn.** Same discipline as
  citable shas: a check-run id is a claim about time.
- **A merged PR's gate is judged at its PR head, not the squash tip.** After a squash merge the verdict
  check runs on the head commit (`d1da6c46`), not the squash sha on `main` — an empty check-run list at the
  squash tip is expected and is not evidence of a red.
- **Mid-flight failures on a PR that later went green are evidence FOR the guard**, not a live defect: the
  stale-straggler class (a body/`SYNC:` fix pushed after a failing run, then the rerun flips it). Report it
  as such and close it; do not re-open, re-push or re-check a merged, read-only vehicle (#824).

## When a lane reports a supersession

A lane reporting "your cited check-run was superseded, current set is all green" is checkable in one API
call — verify it rather than re-arguing, then close the post-merge acceptance point with the live id and
its `completed_at`.
