# Concluding or archiving an OpenSpec change

## The gate red it explains

`make ci-openspec` (and the `linux/openspec` leg) reds when any change under
`openspec/changes/*/` is still ACTIVE and carries unchecked `- [ ]` task boxes. The
failing gate is not a structural problem — the OpenSpec CLI validates every change green
— it is the tasks-check: an active change with open boxes blocks every balanced PR.

Run the change through the CLI to separate the two:

```
openspec validate --changes            # structure: green even when the gate reds
openspec/changes/<name>/tasks.md       # the boxes the gate counts
```

## Which remedy is honest

Decide from the change's real state, not from the dispatch's suggestion:

- **Work genuinely finished** → tick the remaining boxes `[x]` and leave the change
  active (or archive it if the convention is to archive on completion).
- **Work deliberately NOT done** (superseded by a closed issue, deferred to a named
  successor, a refactor whose risk a closed change no longer owns) → tick the box `[x]`
  **with an inline supersession note naming the successor**, and archive the change. Do
  not re-open the closed ancestor's scope, and do not leave the box unchecked (that is
  what reds the gate) — the note is what makes the tick honest.
- **Work still owed** → do not archive. Implement it.

## Archive mechanism

`openspec/changes/archive/` is the reserved directory: the tasks-check script's
`active_change_names` skips any sibling path component named `archive`, so a change
moved under it leaves the active set the gate enumerates. Move the whole change
directory, preserving rename detection:

```
git mv openspec/changes/<name> openspec/changes/archive/<name>
```

That keeps `R100`/`R0xx` rename status in `git diff --name-status` — a delete+add pair
reads as content churn in review.

## The four edits an archival PR carries

1. **Rename** the change directory into `archive/` (above).
2. **`tasks.md`** — every box `[x]`, each deferred one carrying its supersession clause
   (which issue closed it, which PR landed the fix, what remains deferred and why).
3. **`proposal.md`** — append a `## Conclusion (archived — superseded by #<n> closure)`
   section: the state of each What-Changes step (landed / deferred), the successor PR,
   and a sentence on why the change moves to `archive/` so the gate returns rc=0.
4. **The `check-docs` note pair** — `agent-wiki/<date>-<slug>.md` plus
   `docs/changes.d/<date>-<slug>.md` (trailing newline), then `make changes-index` to
   re-render `CHANGES.md`. A changed path under `openspec/` makes the change→note gate
   owe a note (`owes_note` returns `[]` only when an `agent-wiki/*` note is among the
   changed paths in the same commit set).

## Order of operations that avoids the traps

1. Move + edit + write the note pair.
2. **Commit everything in ONE commit** — see the `git add` pathspec trap in SKILL.md: a
   multi-pathspec `git add` naming both the OLD and NEW change path aborts on the
   unmatched old path and silently drops your content edits, leaving a rename-only
   commit. Stage with `git add -A openspec/ agent-wiki/ docs/ CHANGES.md`, or verify with
   `git diff --cached --stat` that the content edits are actually staged before
   committing.
3. Run `make ci-openspec` and read the pass line (`N passed, 0 failed`), then
   `make check-docs` with an explicit `BASE=<main-sha>`.
4. Verify acceptance as **zero remaining active changes that red the gate** — not "the
   one named change is gone". Grep the log for the change name to confirm it is absent
   from the active set.

## Reading the passes/fails line

`grep -c FAIL` on the gate log produces false positives: phase names legitimately contain
"failure" (`census-git-failure-diagnostic`, `run-failure-reactor`). Trust the CLI's own
summary line (`297 passed, 0 failed`) and the make exit code, not a substring count.
