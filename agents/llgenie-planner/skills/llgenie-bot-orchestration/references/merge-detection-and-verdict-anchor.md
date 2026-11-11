# Merge detection and head-bound verdict anchoring

Companion to `references/verifying-lane-claims.md` (which is at its size ceiling); these are the
merge-state and verdict-provenance checks that file is too full to hold.

## `mergeable_state` is not `.state` — a PR you think is open may already have merged

Sampling `mergeable_state` alone and recording the PR as "green, awaiting review" is how a merge
goes unverified: merged and closed PRs commonly report `mergeable_state=unknown` / `mergeable=null`.

Query the three fields together and never infer liveness from the mergeable field:

```bash
gh api repos/<owner>/<repo>/pulls/<n> \
  --jq '"state=\(.state) merged=\(.merged) mergedAt=\(.merged_at // "-") rest=\(.mergeable_state) base=(\(.base.ref))\(.base.sha[0:10])"'
```

A `merged=true` is a merge **event** with its own owed post-merge verification — whatever an
earlier ledger row said. Do not "correct" the row with a note; discharge the verification.

## Merges land out of the order your passes recorded them

Your notes record what a pass saw; main records what happened. A PR your previous pass logged as
"CI green, not merged" can merge before a PR you logged as merged, leaving the earlier one
unverified. Reconstruct the real order from ancestry — each squash commit carries its PR number:

```bash
git fetch origin main && git log --oneline origin/main -n 20
```

Re-verify **every** merge sitting above the tip you last verified, not just the one your notes
flagged. Cheap per run: for each, confirm `baseRefName=main` (a stacked PR did not land on main),
the merge commit's check-runs are `success`, and the acceptance criteria hold at that sha.

## A head-bound verdict or AC write-back goes stale when the head moves — re-anchor before voiding

When a PR is rebased after a reviewer verdict or an AC write-back, **diff the chain first**:

```bash
gh api "repos/<owner>/<repo>/commits?sha=<branch>&per_page=10" \
  --jq '.[]|"\(.sha[0:10]) \(.commit.message[0:50]|gsub("[\r\n]";" "))"'
```

- Same commit subjects reappear on the new base → the content survived; only the provenance anchor
  is stale. Ask the owning lane to re-anchor its verdict/tick at the new head; the hold itself stands.
- Content differs → the verdict is void; a fresh review is owed.

Never re-tick boxes or re-author a lane's verdict yourself: a write-back belongs to the lane whose
head it proves, and a planner edit to it is unattributable at the next audit. Record the owed
re-anchor as a dispatch item on the PR, not as a silent ledger correction.
