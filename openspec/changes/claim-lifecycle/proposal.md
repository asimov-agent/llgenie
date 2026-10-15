# claim-lifecycle — proposal

Issues: [#291](https://github.com/asimov-agent/llgenie/issues/291) (a cancelled run keeps its claim),
[#292](https://github.com/asimov-agent/llgenie/issues/292) (the announced TTL is decoration)

## Why

Every bot now claims the subject it is about to mutate and releases it with a `done` marker
(#279/#285). Two properties of that protocol are decoration rather than mechanism, both measured on
`main`:

- **The marker carries no TTL, so the READER decides how long a claim holds** (#292). A claim for
  minutes of work blocks a PR for the four hours `PR_CLAIM_TTL` says, and the sentence a maintainer
  reads ("leave it alone for the next 4 hours") disagrees with the number the bots apply. The writer's
  `ttl` only shaped the prose (`claim_comment`'s own docstring admits it), and `_say` rounded a
  30-minute window up to "1 hour".
- **The marker names no run, so a dead holder keeps the lock for the whole TTL** (#291). The release
  lives in the LAST step of a run; a cancelled job skips every remaining step, so a cancelled or
  killed run holds its PR until the TTL expires — and the sibling's skip is a log line nobody reads.

## What Changes

- **The marker carries its own terms**: `ttl=<minutes>m` and `run=<id>`, both optional so a marker
  written before this change still parses (and then falls back to the reader's default).
- **`occupied()` honours the announced TTL**, with the caller's value as the legacy fallback: a
  30-minute claim no longer holds for a reader that would age it for four hours.
- **A reader that can ask releases a claim whose run is over**: `is_live=` takes the caller's probe,
  `run_is_live(gh_call, run_id)` reads `gh run view <id> --json status,conclusion`, and a run that is
  `completed` (cancelled, killed, out of budget) frees the subject at once. **An unreadable state is
  `None` and never releases a claim** — "we could not check" is not "it is gone".
- **`released()` makes the takeover loud**: it names the holder and why it is gone ("its run N is no
  longer running", "the claim announced 30 minutes and that has passed"), and all four pickers print
  it when they take a subject that had a claim.
- **Every writer passes `run_id`** (`GITHUB_RUN_ID`) and its own `ttl`; `cancelled` joins the
  release words, so a run that stops without finishing can say so explicitly.

## Deliberately not done

- **No `if: cancelled()` cleanup step in the workflows.** GitHub runs such a step best-effort, after
  the cancellation has already been requested — the liveness check is the reliable half (it works even
  when the runner is gone without a last word) and it needs no workflow change at all.

## Not covered

- #293/#294/#296 — the reviewer bot's blind spots and the queued-run alarm's delivery, each its own
  change.
- Any *new* concurrency protection: this fixes what the existing protocol promised, it does not add a
  lock.

Refs: #279 (the protocol), #285 (the PR subject), #289 (the push-cancellation that makes #291 bite).
