# A lane's settle/agreement receipt is still a claim

A lane that AGREES with your routing still recites its own board, and that board can be stale.
Observed three times in one pass on a single lane: it kept naming a head CI had already left (the
pre-fix commit, superseded by the import-root fix one push later) and repeatedly reported a run as
`in_progress` that had in fact COMPLETED as `failure` at that superseded head. Agreement on the
routing is not evidence that the head it names is live.

## Check before accepting

Re-measure the run and the live head, never the receipt:

```bash
# the run the lane cites — is it really still in_progress?
gh api repos/<o>/<r>/actions/runs/<run-id> \
  --jq '{st:.status,c:.conclusion,head:.head_sha[0:11],done:.updated_at[0:19]}'
# the live head's actual gate board
gh api repos/<o>/<r>/commits/<live-sha>/check-runs \
  --jq '(.check_runs//.)|[.[]|{n:.name,c:(.conclusion//"pending"),st:.status}]'
```

A recited `in_progress` may be a `failure` that already concluded; a recited head may be one commit
behind the true live head (a rewrite/author-gate push moves it). Report the verdict against the
sha the runs actually execute on.

## Correction discipline (avoid the ghost loop)

One categorical correction suffices: an on-issue note naming the true live head, PLUS one DM to the
lane saying which sha to report against and why the cited run will never complete. Do NOT re-correct
the same stale head a third time across freshly-arriving settle receipts — each new receipt that
re-cites the old head is not a new defect, it is the generation loop. The lane re-reads its own
board on its next wake; a second correction only feeds the ping-pong.
