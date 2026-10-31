# Dispatch and handoff

A dispatch that does not land is not a dispatch. Tonight roughly a third of this lane's messages returned
`queue_full`, and the difference between a lost instruction and a delivered one was almost never visible
from the sending side. These are the rules that survived.

## Make the dispatch survive the mailbox

- **Post the dispatch on the issue or PR as well as sending it.** A comment is durable, findable by a
  stranger, and survives a full mailbox. Twenty-plus `queue_full` failures in one evening produced zero lost
  instructions only because every one had a comment behind it.
- **A queued message is not a landed task.** Report the delivery id and then the evidence: branch, run id,
  PR number. If the only evidence is "I sent it", nothing has been handed over.
- **Repeat the assignment in every follow-up.** A lane's context is its own; assume it does not remember what
  you asked three messages ago, and restate the id, the scope and what "done" means.
- **Name the one action.** When a lane is looping, a message with five observations produces five more
  messages. "Cherry-pick 706e3b27, then `grep host_bot_capabilities`" is a dispatch; a paragraph of context
  is a discussion.

## Respect the gates you meet

- **A lane's versioned SOUL outranks your dispatch.** When a lane declines because its charter forbids the
  act — arming, merging, approving — record `auto=none (lane charter: <path>:<lines>)` and stop asking. Ask
  once for the line; quote it in the record; never re-request.
- **A lane's owner-word calibration is a gate, not a delay.** Record it as `held on the owner's word` rather
  than as a missing action, and route the work where it can move instead.
- **Do not re-cut or force-push another lane's branch.** A rebase lane that races an actively-pushed author
  wastes both lanes; the correct outcome is that the branch lands later with its deviation documented.
- **When two lanes are on one file, name the owner before either pushes.** Tonight two lanes' PRs both claimed
  the same generator fix. Checking the actual diffs showed only one contained the file — the collision was in
  the intent, not the code, and it dissolved once measured.

## Feedback loops that quietly stop

- **A producer that advances state before delivery cannot distinguish delivered from lost.** Write an
  append-only outbox before returning, and stamp every emitted line with its measurement time. Otherwise a
  `queue_full` failure destroys the alarm permanently and the next pass re-emits a stale task list that looks
  current — the orchestrator tick did exactly this four times in one evening.
- **A detector whose "nothing found" and "couldn't tell" print the same thing will silently stop watching.**
  Reduce an `UNKNOWN` answer through a direct measurement (`git merge-tree`) instead of reporting it as empty.
- **A monitor gate makes false negatives persistent**, because byte-stable wrong output suppresses the very
  tick that would catch it. Quiet is only meaningful if quiet was *measured*, not assumed.

## Composing the report

- Quote the head and the minute together; where the head cannot be re-read in the call that writes the line,
  write `pending at <hh:mmZ>`.
- Keep buckets separate: `13 success` and `13 success + 1 cancelled` are the same number of failures and
  different states of knowledge.
- State what is blocked, by whom, and the checkable condition that unblocks it. "Holding" without a named gate
  is indistinguishable from neglect on a board.
