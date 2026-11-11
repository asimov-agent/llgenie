# A queued lane DM can arrive out-of-order

A lane's asynchronous DM is a claim about the moment it was queued, not about now. It can land *after*
the lane has already posted a newer on-issue comment that supersedes it — so the DM's refs may be stale
even though nothing is wrong on the wire.

Symptoms seen in practice:
- The DM names a branch HEAD sha that is an **orphaned pre-rebase tip** — the lane force-pushed a rebase
  onto a newer base after queuing the DM. `git fetch` the branch and compare: the remote tip differs from
  the DM's sha, and the DM's sha's parent chain sits on a superseded base (e.g. an old union commit that a
  canonical rebase replaced).
- The DM cites a **comment id that 404s** — the lane replaced or deleted that comment (often a
  draft/duplicate) and reposted under a new id.

## Check before you correct

Before posting a correction to a DM's stale refs, list the lane's newest comments on the issue:

```
gh api repos/<owner>/<repo>/issues/<n>/comments --jq 'sort_by(.created_at)[-3:][] | "\(.id) \(.created_at[0:16]) :: "+(.body[0:70]|gsub("\n";" "))'
```

Adopt the **newest on-wire comment** as the authoritative record. If the lane already superseded the DM
itself (its newer comment documents the rebased head / replacement comment id), do **not** post a
correction — the newer comment is the record and your post becomes crossing traffic that the next reader
must untangle. Only correct when the newest comment still carries the wrong fact.

Corollary: never propagate a DM's sha or comment id into your ledger or a dispatch without first
confirming it against the current remote tip and the issue's comment list. "The lane said X" is a claim;
`git rev-parse` on the fetched branch and the comment API are the evidence.
