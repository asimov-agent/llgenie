# Answering an automated probe about your own turn

Reflective probes (a nerve/guard check, a "did this turn change anything" review, a verdict
hook) assert a fact about your turn: *"no task-relevant change happened"*, *"the claim is
unverified"*, *"the work is incomplete"*. **A probe's assertion is a claim, exactly like a bot's
report** — it describes its own scan window, not the state of the board. Answer it as evidence,
not as an instruction.

## Procedure

1. **Name the exact object the probe says is missing.** A comment, a label, a branch head, a run,
a file. Not "the issue" — the id.
2. **Re-read it from the API in this turn**, and quote the identifier back:

```bash
gh api repos/<o>/<r>/issues/<n>/comments?per_page=100 \
  --jq '.[] | "\(.id) by=\(.user.login) \(.created_at[0:16]) :: \(.body[0:52])"'
gh api repos/<o>/<r>/commits/<sha>/check-runs \
  --jq '[.check_runs[]|"\(.name): \(.conclusion // .status)"]'
```

3. **If the mutation is already landed, say so with its id.** The answer to "nothing changed" is the
comment id, the head sha, the run id — quoted, not restated from memory.
4. **Never manufacture a redundant write to satisfy the probe.** A fabricated "activity" comment is
worse than a false complaint: it puts a meaningless entry on the trail, quietly teaches the next
reader that the substantive one did not count, and burns a never-merge/never-push boundary to
satisfy a scanner. Probing redundancy is not a reason to invent work.
5. **Report a measurably wrong probe as the finding.** If the premise is refuted, that is the
result worth surfacing — a probe that cannot see landed mutations will keep firing and will keep
pushing every lane toward fake activity.

## When the guard demands a mutation and an earned one exists

"Do not manufacture a redundant write" does not mean "do nothing" when the turn genuinely produced
a finding. If this turn measured something new that the board should carry anyway — a re-anchor
landed (`behind_by` went 2 → 0), a merged-tip run finally dispatched, a stale fact corrected —
posting *that* as a read-back-verified comment is the earned mutation: it is work you owed
the issue independent of the probe, not activity invented to satisfy it. The distinction is the
provenance of the content, not the presence of a write: an earned finding posted is fine; a
"still here, nothing changed" placeholder is fabrication.

- **A guard that blocks one call in a parallel batch did not fail the read.** When several read
  calls go out together and the guard kills one with the progress-blocking error while siblings
  return data, the dropped call's info is simply missing — re-issue that one read standalone
  (the guard's scan does not always catch every sibling), do not conclude the target is absent.

## Pitfalls

- **A `404` on a single comment id is not proof the comment is absent.** Read the *list* endpoint for
the issue (`.../issues/<n>/comments`) — it is the authority for "does this comment exist on the
trail". A per-id read that 404s while the list shows the id means you read the wrong object type
(issue-comment vs review-comment) or the wrong repo, not that the post failed.
- **A successful `gh api` POST is not a landed post** — re-read the list and find the id before
you call it reported.
- **Do not answer a probe by widening scope.** "Prove you did something" never authorises a push to
another lane's branch, a merge, an arm, or an unrequested edit. The answer is evidence about what
was already done, or a dispatch that sends the work to the lane that owns it.
- **A recurring probe is a signal about the probe, not about you.** If the same complaint fires
several times in one pass against a state you have verified, stop re-verifying and record the
refutation once, on the board, with the ids — then move to the next real dispatch.
