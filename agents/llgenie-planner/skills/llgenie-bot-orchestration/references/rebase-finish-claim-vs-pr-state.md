# A lane's "rebase finished, new head <sha>" can coexist with a CLOSED, zero-diff PR

A rebase lane posting "finish — new head `<sha>`, force-pushed to the same branch" is a claim about
what it *intended*. The live `pulls/<n>` can read `state=closed`, `head=<main-tip>`, `commits_count=0`,
`additions=0` — the PR was closed and its head force-pushed to main's tip, leaving a zero-diff closed
PR that no longer takes a merge, and the finish comment can even post *after* the close event. Never
accept "rebase done" from the head sha alone; read the PR's `state` and its event timeline:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{state,closed,h:.head.sha[0:8],b:.base.sha[0:8],commits_count:.commits,additions,deletions,merged_at}'
gh api repos/<o>/<r>/issues/<n>/timeline --jq '.[-8:]|map("\(.event) \(.created_at[11:19]) \(.actor.login) \(.commit_id[0:8]//"")")|.[]'
```

`state=closed` + `merged_at=null` + `additions=0` while the lane reported a rebased head = the PR was
closed and the branch reset, NOT merged. But **closed ≠ content lost**: read the branch tip directly —
`git ls-remote origin refs/heads/<b>` may still hold the correct rebased commit (parents[0] == live
main), a sha the API's `head.sha` field does not surface once the PR is closed and reset. Distinguish
"content destroyed" from "PR closed, branch content safe at a sha the API no longer reports" before
escalating the scary version.

Recovery is `gh pr reopen <n>`, then re-read `head`, `commits_count` and `mergeable` to confirm it
resolves to the rebased sha with a real diff and MERGEABLE; if the reopen resolves to the reset head,
the lane must re-push the surviving rebased sha. A lane's reply can come back truncated (empty
transport body) — do not read emptiness as "nothing happened"; measure the wire. Dispatch the lane to
state who/what closed it at that timestamp and post the corrected state on the PR, so the close is
not mistaken for a merge by the next reader, and the PR is left open+mergeable for the owner path
(you never merge/arm — #1088).

## The close-vs-merge distinction on a rebound branch

`gh api pulls/<n>` returning `merge_commit_sha` non-null does NOT mean merged — that field is a
GitHub-computed potential merge commit and exists on open/closed PRs alike. The merge facts are
`merged_at` (null = never merged), `state`, and `merged_by`. A closed PR with `merged_at: null` whose
content you confirmed absent from `main` (`git show origin/main:<path>` fatal) was **abandoned, not
landed** — report it as an incident-shaped finding, not a merge.
