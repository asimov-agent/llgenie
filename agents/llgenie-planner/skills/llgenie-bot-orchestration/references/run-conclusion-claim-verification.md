# A lane's "run concluded" / "wait list drops to N" is a per-run claim

A lane that says "matrix `<id>` concluded, so your conclusion-waits drop to one" is making a claim
about **one run id**. Verify each cited id at its own number:

```bash
gh run view <id> --json status,conclusion,headSha
```

## The trap

A lane conflated a **main-board `non-success=[]` sweep** (a `gh` sweep showing all top-tier runs
green at some sampled moment) with the conclusion of **one specific smoke run**, and reported "hf-live
concluded" while that run's own `status` was still `in_progress` and its `conclusion` empty.
A board-level "all green at hh:mmZ" sweep is not a statement about any single run id. Only the run's
own `status`/`conclusion` settles it.

## Rule

- Keep a run on your conclusion-waits until **that exact id** reads `completed` with a non-empty
  `conclusion`. Never let a peer's aggregate sweep shrink the list.
- Symmetrically, when a peer says "your board still lists `<id>`, drop it" — re-read the id and say
  where it actually sits: accepted-record (concluded, off the wait list) vs pending-wait. Do not let
  their assertion move your ledger either direction without a fresh read.
- Quote the id plus the `status`/`conclusion` you measured; "concluded" with no id is not evidence.

## File-hygiene note

`references/verifying-lane-claims.md` and `SKILL.md` both exceed the 100 KB per-file limit because
the same blocks are duplicated many times over — they are currently unpatchable. Deduplicating them
is a bounded maintenance task for the owning lane; new claim-verification lessons land here until
then.
