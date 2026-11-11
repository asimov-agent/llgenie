# Auditing an open-issue queue for validity (still-valid / no-PR / stale)

When the user asks "are the reported issues still valid and current, and which have no
PR yet?", the answer is a live repo/API audit, not a reading of the issue list. Do it
in this order so the report is grounded and the queue stays trustworthy.

## Procedure

1. **Fetch the repo tip AND the full issue+PR surface first.** `git fetch origin
   --prune`, then pull `gh issue list --state open --limit 200 --json
   number,title,labels,createdAt` and `gh pr list --state all --limit 300 --json
   number,title,body,state,headRefName` in one batch. A PR can be MERGED (issue
   actually fixed) or OPEN (in flight) — both change whether an issue still needs
   work, so pull `--state all`, not just open.

2. **Map issues to PRs by reference, not by name.** For every PR (open AND merged), scan
   `#\d+` refs in title+body+headRefName; union the sets per PR. An issue with an OPEN PR
   is in flight (skip); an issue whose term appears in a MERGED PR is claimable as
   fixable-cheap but verify it actually closed. Issues in neither set are the live queue.

3. **Classify each no-PR issue against the CURRENT tree, not the issue prose.** The
   issue text was written sometime else; a fix may have landed without closing it. For
   each issue, grep the actual code for the offending symbol/flag/path the issue names
   and decide: **still valid** (the defect is present), **partial** (the headline
   symptom is fixed but the issue's stated Done-when is not — e.g. a mount fix landed
   but the guard it asked for did not), or **dup/already-fixed** (a sibling issue or PR
   carried the identical fix).

4. **Normalise the duplicates.** A repeated gap signal is one work item; only the newest,
   correctly-labelled one should carry the bot trigger label. Recommend closing the
   older dupes / re-scoping a partial, so the queue counts once.

5. **Report grouped by verdict, with the evidence.** One row per issue, its verdict
   (still-valid / partial / dup / overtaken), and the grep line that proves it. The
   user reads the verdict + evidence, not a re-stated title. Lead with what is DONE and
   merged, then the live queue, then the dups to consolidate.

6. **Fix the smallest first, one at a time, each off a fresh base.** Per issue:
   `make worktree-new` off the freshly fetched `origin/master`, make the tracked OpenSpec
   change, prove the new test red-on-old (`git show origin/master:<file>`), green-on-new,
   run `make test`/`lint`/`openspec-check`/`architecture-check`, commit, push, open a
   NON-draft PR (`closes #<n>`, no `--draft` — a draft excludes squash+auto-merge).

## A queue that reports "empty" while it is full

When the answer to "why is nothing being implemented?" is a green sweep saying `candidates=0` /
`backlog empty`, treat that as a claim to verify, not a fact. Three shapes, all silent:

1. **A LABEL-ONLY hold has no timestamp, so it holds for ever.** A queue that skips issues carrying
   a decision label (`agent:refined` / `agent:closed`, an operator verdict) parks them permanently —
   by design, if releasing one is a human's act. The defect is the SILENCE: the skip-note path only
   knew the reviewer's *verdict* hold, so it printed "nothing to note" while the pick held every
   candidate. When auditing, run the picker and the note separately and compare: if the picker says
   `position=-1 reason=decided:<label>` and the notifier says nothing holds the queue, they read
   different rules.
2. **Date a decision from the MARKER, not the label.** A comment written when the verdict was
   applied (`<!-- <bot>-verdict: <kind> <ISO8601Z> -->`) is the only timestamp that exists, and it
   is what lets a queue say *when* the hold started. A hold a human must release is still announced
   on the issue — the human who can release it reads the issue, not the bot's log.
3. **A shared parser must scope an optional field to the ONE marker that has it.** Teaching a
   generic marker regex `<!-- name: [<word> ]<TS> -->` makes a marker whose NAME CARRIES A WORD
   (`issue-review: window <TS>`) parse as the shorter marker (`issue-review`) — the exact confusion
   the registry exists to prevent. Keep per-marker shape overrides in an explicit set
   (`FIELDS = {("bot", "kind")}`), never as an optional group on every marker, and assert the
   two near-miss markers still parse differently.

The general audit move: grep the tree for the marker literal a bot WRITES. A registry that only
checks `registered -> has a writer` cannot see a marker written OUTSIDE the registry, so a reader
needing its timestamp hardcodes the literal and drifts. Both directions must be guarded.

## Pitfalls

- **The API is the source of truth for "has a PR", the issue list is not.** A search by
  title strings misses a PR whose body carries `Closes #N` without the number in the
  title; a PR auto-merged by qa-validate's `auto-merge` can land without a human ever
  closing the issue. Always cross-map through `#\d+` refs in the body.
- **An issue "fixed without closing" reads as valid.** When a MERGED PR touches the
  symbol an open issue names, verify whether that PR's diff actually satisfies the
  issue's Done-when — a mount added to `TEST_RUN` may fix the headline while the
  issue's guard request goes unmet, so the issue stays correctly open but set to a
  narrower scope.
- **Duplicate gaps hide behind per-run timestamps.** Several issues for one gap (each
  carrying its run timestamp in the title) look like several gaps. Compare the non-`est`
  signature across them (the label + the keyword after `data-gap:`), and only ever
  keep the one with the bot-trigger label as the implementable row.
