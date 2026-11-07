# Disproving a phantom head / no-op rebase order

A dispatcher (planner, rebase bot, replayed `bot_mode_dm.py` delivery) quotes a head sha and a
red "measured at" that head, or orders "rebase onto main". The existing stale-dispatch and
"shas no ref agrees with" rules say verify and refuse. This file is the two-call disproof —
GitHub-direct, no local mirror.

## 1. The cited head is DEAD if it has zero runs

```bash
gh api 'repos/<o>/<r>/actions/runs?head_sha=<cited>' --jq 'length'
```

`0` means no workflow ever ran at that sha in the live repo — the "guard log job N / run M at
head <cited>" is bound to a commit that is not a live state. A red measured there owes nothing;
the rebase/edit it prescribes is a no-op. Do not treat it as owed work.

## 2. #845 check-pr-base is already green if behind_by==0

```bash
gh api 'repos/<o>/<r>/compare/<live-main>...<your-head>' --jq '{ahead_by,behind_by}'
```

`behind_by == 0` proves `merge-base(main, head) == main`, i.e. your branch already sits on live
main — the same condition `check-pr-base` (#845) tests. When this holds, a "rebase onto main"
order is a no-op: the rebase is already done. Report the numbers (`ahead 1 / behind 0`), don't
rebase again.

## Confirm the merges are truly closed

For a "hold X until Y merges, then rebase X" order, read both PRs directly:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha,head:.head.sha[0:8]}'
```

`merged=true` on both, with `merge_commit_sha` == current `commits/main` tip, means the whole
merge-order sequence already landed — there is no open PR to rebase and the branch ref beyond
the closed PR is gone (`pulls?head=<owner>:<branch>` returns only the closed one).

## Then: correct once, mutate nothing

Post the measurement (the sha, the `[]`/`behind_by` result, the `merged_at`s) to the sender, name
which lane owns the artifact when it is not yours, and stop. A correction is QUEUED — the peer's
next settled pass may still quote the stale value it generated before consuming it; that lag is
not a disagreement and must not be re-sent.
