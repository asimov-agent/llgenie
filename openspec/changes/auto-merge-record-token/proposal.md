# Proposal: auto-merge-record-token (issue #2953)

## Why

The sweep recorder landed on `main` (PR #2951, squash `3b6d33af04`) posts its tracker
comment on #2652 with the ambient `GH_TOKEN=secrets.BUMP_TOKEN`, but the owner PAT
behind `BUMP_TOKEN` cannot create ISSUE comments. Measured on main
`f71e48e25153b07d71ba72185fc182117c51ab27`: auto-merge runs 44658425503, 44658824660,
44658940504, 44659822138, 44661942440 and 44664497025 all concluded `failure` at the
`recheck` job with `GraphQL: Resource not accessible by personal access token
(addComment)`, and `ci-verdict` (run 44664498485, check-run 136050586819) answers
UNJUDGED RED because of that red `recheck` check-run. PR-level comments from the same
PAT (deferrals, merge announcements) work — only the issue comment fails. The recorder
made the sweep's own bookkeeping fatal to the merge lane: every main push now carries a
red verdict lane, and the #2652 tracker receives no CI-side records.

## What Changes

- `scripts/auto_merge.py recheck` posts its `--record` comment through the existing
  `_gh(..., token=...)` environment-only seam with a `RECORD_TOKEN` override: when
  `RECORD_TOKEN` is set in the environment, the issue-comment call runs with
  `GH_TOKEN=<RECORD_TOKEN>`; every other call keeps the ambient token. Without
  `RECORD_TOKEN` (host runs), behaviour is byte-identical to before.
- The `auto-merge.yml` recheck sweep step sets `RECORD_TOKEN: ${{ github.token }}`.
  The workflow's `permissions:` block already carries `issues: write`, so
  github-actions[bot] may post the tracker record while the merge itself stays on the
  owner PAT — the two-identity doctrine of #874 extended to issue comments.
- Tests: the fake-gh harness captures the environment token of its `issue comment`
  calls; a new test pins that `RECORD_TOKEN` reaches exactly the record call and the
  ambient token still posts everything else.

## Out of scope (filed as linked issues)

- Owner decision on the PAT itself: widening `BUMP_TOKEN` to `Issues: Write` is an
  owner-level secrets choice, filed as [#2954](https://github.com/asimov-agent/llgenie/issues/2954).
- Historical red `recheck` check-runs on already-pushed main heads stay as history;
  the fix lands clean verdicts on NEW heads only.
