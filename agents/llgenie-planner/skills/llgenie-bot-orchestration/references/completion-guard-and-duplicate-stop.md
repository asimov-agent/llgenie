# Finishing a pass, and confirming a duplicate-stop

Two rules that decide whether an orchestrator pass actually ends correctly.

## Finishing a pass under the completion guard

The session's completion guard can fire at end-of-turn: it **pauses read/search/test tool calls and demands a
task-relevant mutation**. Satisfy it with a genuine mutation your own seat owns — never by widening scope to fit the
guard, and never by manufacturing a change to look busy.

Legitimate mutations for this seat:

- **Refine an issue you own into a testable acceptance rubric.** Turn a finding into numbered, verifiable criteria the
owning lane can implement and a reviewer can check in one pass. A finding with no acceptance rubric is not yet
dispatchable — the refine step is the core of the role, so this is real work, not a way to appease the guard.
- File or correct a tracker issue (placeholder `closes` targets, stale scope, a superseded duplicate -> close with a
  comparison).
- Post a routing/refinement comment on the board so ownership and "done" are visible without re-deriving them.
- **Complete the un-performed half of a duty you already opened.** If a previous pass bound an acceptance
  contract, told a lane to self-report against named criteria, or promised a re-measure, the owed mutation is
  the verification behind it (read the diff against the criteria; re-fetch the run/job state), not a
  restatement comment in new words. A pass that re-states an earlier verdict is padding; one that closes a
  loop it left open is real work.

Never: a peer-lane edit (fold, push, rebase on another lane's branch), a fabricated status, or destructive cleanup.

Because reads are paused while the guard is up, decide the mutation from context you already hold, then act. A
scratch or unrelated file will not clear the guard — the mutation must point at the real work. The lane's own
durable **pass record** (the running file of verified fleet state in the profile cache) IS a legitimate in-seat
mutation, distinct from a throwaway scratch file: appending a verified post-merge disposition there keeps the fleet
state from being lost and is real work. And record its proof (comment id, read-back): a mutation the guard forced is
still a claim until you verify it landed.

### REPLAN control: a repeat refusal is about the command, not the finding

When a mutation fails for a reason unrelated to the finding (transport, guard interference) and the guard then
replies `prevents repeating the exact action that already failed`, do **not** re-issue the identical command — the
verbatim retry is the thing it is refusing. Pick a materially different mutation of the SAME finding instead:
post to the correct owner tracker (not the one you tried), or record the verified disposition in the pass record.
Re-loading run state before choosing is what makes the second attempt different rather than a loop.

## A stop is confirmed by measured absence, not by a delivered DM

When you tell a lane to abandon a duplicate vehicle (a branch/PR that re-fixes something already merged), the DM is
only a delivery attempt. It can report `queue_full` or land ambiguous, and an out-of-order report may never reflect it.

So:

1. Post the stop **durably on the tracked issue** so it exists for the next reader regardless of DM delivery.
2. Confirm the stop by **measuring the vehicle's absence** — `git ls-remote origin '<branch>'` empty, and
   `gh pr list --state open` showing no such PR — not by assuming the lane read the message.

A duplicate that was never created is closed by absence. State it with the command output: "I told it not to" is not
evidence it did not.
