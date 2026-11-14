# The issue-bot pick must refuse issues whose lane branch already exists (issue #2671)

## Why

`make issue-bot-dispatch` computes the branch `agent/issue-<n>-<slug>` in
`scripts/issue_implementer.py::dispatch()` but never checks whether a branch under that
prefix already exists on the remote. The bot's pick therefore collides head-on with branches
lanes create for the same issue (`AGENTS.md`'s `agent/issue-<number>-<slug>` is the branch
shape lanes use). Measured on issue #744: lane branches `agent/issue-744-ci-security-p0-finds-are-issues-415-416-417`
and `agent/issue-744-ci-issue-bot-picks-736-737-738` exist; every issue-bot dispatch since
11 Nov picks #744 (it is the oldest open `agent:implement`), the agent leg runs ~40 minutes,
and the run dies at commit+push (`[rejected] ... (fetch first)`) with no PR.

The claim/occupancy logic in `_pick_free` reads only comment markers
(`scripts/bot_claims.py`); a pre-existing remote branch is invisible to it. That gap is a
burning, not a cosmetic miss: each doomed dispatch spends a full implement leg (agent runtime,
JEV tokens, minutes) and 3 dispatches in the last 48h were known-bad.

## What changes

- `scripts/issue_implementer.py` gains `_remote_lane_branches(gh, repo, num)`: a probe of
  `gh api repos/<repo>/git/refs/heads/agent/issue-<n>` (the refs prefix endpoint) that returns
  the remote branches carrying `agent/issue-<n>` or `agent/issue-<n>-…`. A 404 (no branch) is a
  legitimate answer, so the probe does NOT go through `_gh` — that would turn "no branch" into a
  SystemExit.
- `_pick_free` treats an existing lane branch like a live claim: it prints a named skip
  (`branch-exists`, naming the branch) and takes the next candidate.
- `dispatch` reports the skip: when every remaining candidate was branch-skipped it returns
  `{"action": "none", "reason": "branch-exists", "skipped": [...]}` and the CLI prints
  `reason=branch-exists`; the workflow already maps `action=none` to `dispatch=false`, so the
  implement leg never starts. A forced dispatch (`FORCE_ISSUE`, label/manual pin) is refused the
  same way for the same reason instead of burning the leg.
- `tests/test_issue_implementer.py` seeds a foreign `agent/issue-<n>…` branch into the `gh`
  fixture and proves: the pick takes the next issue; a fully branch-covered candidate set yields
  `action=none` with `reason=branch-exists`; a forced pinned issue with a lane branch is
  refused; and a candidate set with no branch answers unchanged (404 must not crash the pick).

## Open items

None. Clearing the existing squats (#744's two lane branches and the 6 phantom runs) stays
owner territory — #2606 tracks the runs; the branches belong to their lanes' PRs.
