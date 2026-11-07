# PR-shape gates: `check-pr-base` and `check-pr-agents-line`

Two gates wired into the `guard`/`holds` jobs red a PR whose CONTENT is fine. Both read facts outside the diff (git ancestry; the live PR body), so a code push alone never clears them.

## `check-pr-base` — the branch must be cut from `origin/main` itself

Rule (see `scripts/check_pr_base.py`): **`git merge-base <base> <head> == <base>`**. The branch adds commits on top of `origin/main` and nothing else.

Why it reds a MERGEABLE PR: once `main` advances under a branch you cut from an older tip, `origin/main` stops being an ancestor of your head. The gate then refuses the branch *shape*:

```
[check-pr-base] FAILED: <head> is NOT cut from <base> — its merge-base with <base> is <older sha>, not <base> itself … (issue #845)
```

`mergeable:true` is NOT a pass for this — mergeability tests conflicts, this tests ancestry. Do not read MERGEABLE as "no rebase needed."

Cure:

```
git fetch origin main
git rebase origin/main
# re-run the local gate suite, then:
git push <remote> <branch> --force-with-lease=<ref>:<old-head>
```

Pass condition after rebase: `git merge-base HEAD origin/main == git rev-parse origin/main` (both print the same sha). Because the base genuinely moved under you, this rebase is #1015-justified, not churn. Confirm the trigger first:

```
gh api repos/<repo>/pulls/<n> --jq '{mergeable, base: .base.sha}'
```

### A long-lived branch meets this gate once per main merge, not once

Reconciling a branch over a long session means `main` keeps advancing under it (other lanes merge
while you work). Every one of those merges re-breaks the ancestry even though your diff never
changes, so the same PR can red `check-pr-base` two or three times in one session. Each time: re-fetch
`+refs/heads/main:refs/remotes/origin/main`, confirm the new tip is not an ancestor of your head,
rebase, re-run the fast gates, re-point the `AGENTS:`/`BASE:` lines, and force-push with a lease
pinned to the head the PR currently shows. Do not predict the base from a sha quoted in a chat or a
planner message — it is stale by the time you read it; measure the live ref.

### `mergeable:false` with a null `mergeStateStatus` right after a base move is a recompute, not a conflict

GitHub recomputes mergeability asynchronously. Immediately after `main` moves you can read
`{"mergeable": false, "mergeStateStatus": null, "mergeable_state": null}`, which looks like
`CONFLICTING` but is not. Re-poll the same query after a short wait and require BOTH a non-null
`mergeStateStatus` and an actual conflict report before you rebase for conflict reasons — the
ancestry check above is the real trigger, and it is computed locally in one command.

## `check-pr-agents-line` — the PR body must cite AGENTS at a reachable sha

A bot PR body must carry an `AGENTS:` line naming a `BASE:` sha that is reachable from BOTH head and base. The gate reads the LIVE PR body on every run, so the fix is `gh pr edit <n> --body-file <f>` — a code push does nothing.

The cited sha must be an ancestor of both sides (e.g. your fork point, or a main commit still on main after your rebase). A sha that is no longer an ancestor of the base makes the line unreachable and reds again — re-point it after any rebase.

Verify locally before claiming the fix:

```
python3 scripts/check_pr_hygiene.py agents-line --head <head> --base <base> --body-file <body>
# → [check-pr-hygiene] OK: the `AGENTS:` line is reachable from both head and base
```

### Do not hand-write the line — paste the literal `make bot-preflight` output

The gate parses the line's FIELDS, so an invented or abbreviated line reds even when its sha is
correct. Generate the canonical pair:

```
make bot-preflight          # prints, from the live refs on disk:
#   AGENTS: <40-char-base-sha> <7-char-tree-sha> <N>l
#   BASE: <40-char-base-sha> (== origin/main at open)
```

Paste those two lines VERBATIM into the PR body (`gh pr edit <n> --body-file <f>`). Failure shapes
that red the gate: an abbreviated sha (`0fdcd93d6589`), a missing tree field, or a made-up tail
(`… 0fdcd93d6589 census-ok`) — the third field is the tree sha plus a `l` line count, not free text.
Re-run `make bot-preflight` AFTER the rebase/amend and after re-rendering `CHANGES.md`: it reads the
current `origin/main` and worktree, so a pair generated before the base moved names a sha that is no
longer an ancestor of the new base and reds again. The body edit does not change the tree, so it
needs no push — but a push that changes the head does require the sha re-measured.
