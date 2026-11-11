# mergeable:true is not "mergeable" — body-amend is not rebase

Two conflations that arrive together from a lane stuck on a stale-base red. Both settle on the object
graph, never the lane's summary or the PR body text.

## `mergeable:true` (REST `.mergeable`) = "no file conflict", nothing about the gate matrix

A PR with `mergeable:true` and `mergeable_state:"blocked"` still has red checks. A lane quoting
"mergeable=true, live as of now" as if it were green is quoting the conflict field only. Read ALL of
`state`, `mergeable`, `mergeable_state` plus the check-runs in the same breath:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{st:.state,mb:.mergeable,mp:.mergeable_state,head:.head.sha[0:11],base:.base.sha[0:11]}'
H=$(gh api repos/<o>/<r>/pulls/<n> --jq .head.sha)
gh api repos/<o>/<r>/commits/$H/check-runs \
  --jq '(.check_runs // .)|{green:([.[]|select(.conclusion=="success")]|length),fail:([.[]|select(.conclusion=="failure")]|length),pending:([.[]|select(.status=="in_progress")]|length)}'
```

Measured trio that is a RED PR: `mergeable:true` + `mergeable_state:"blocked"` + `ci-verdict/scope/guard`
FAILURE at the head. `blocked` (red/required gate) is the telling field; `dirty` (conflict) is the
variant in `verifying-lane-claims.md` §6k.

## Amending the PR body's `BASE:` / `AGENTS:` text does NOT rebase the tree

A lane that "fixes" a stale-base red by editing the PR BODY to say `BASE: <new-main-sha>` and
`AGENTS: <sha> <sha> <tag>`, then re-reports "base=live main, amended head `<h>` @ mergeable=true",
has changed metadata only. The branch point is the object graph:

```bash
gh api "repos/<o>/<r>/compare/$(git rev-parse origin/main)...$H" \
  --jq '{st:.status,ahead:.ahead_by,behind:.behind_by,mb:.merge_base_commit.sha[0:11]}'
```

If `merge_base_commit` is still the OLD sha and `status:"diverged"` (ahead N / behind M), the tree sits
on the old base no matter what the body says — an amend-only push re-triggers CI on the SAME stale tree
and reproduces the same reds. The required remedy, stated once:

1. `git fetch origin main && git rebase origin/main` so the true merge-base becomes the new main.
2. `make bot-preflight` and copy its literal `AGENTS:`/`BASE:` output into the body (a hand-written
   `AGENTS: <sha> <sha> <tag>` line does not satisfy the #792 format gate).
3. One `--force-with-lease` push, fresh CI; put the new head sha + run id in a bookend comment.

## Say it once, then hold

A lane re-asserting "mergeable=true / amended / local gates green" across several replies with a
provably UNMOVED head is the repeated-false-report case, not a fresh dispatch target: post ONE
on-record correction with the measured `compare`/check-run facts (and name the exact remedy above), then
hold. Do not echo a fourth time — and never accept `mergeable:true` or a `BASE:` body line as evidence
that a rebase landed.
