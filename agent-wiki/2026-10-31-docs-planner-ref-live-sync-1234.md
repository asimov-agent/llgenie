# Version six planner orchestration references live→tree (byte-identical) (#1234)

## What shipped

Live→tree sync of **six** planner-lane versioned references under
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/` (the live-longer slide record
measured in #1234). Each tree file is now byte-identical to the live authoritative file at the head
(`git diff origin/main:<path> <live>` empty; `git show <head>:<path> | wc -c` = live bytes):

| file (live-longer) | tree @ base `45a04c3c` (bytes) | head / live (bytes) |
|---|---|---|
| `agent-behaviour-versioning.md` | 9782 | 10125 |
| `change-note-gate.md` | 2018 | 2590 |
| `ci-gate-vs-live-pipeline.md` | 7246 | 9020 |
| `completion-gate-and-test-run.md` | 2499 | 5700 |
| `rebase-and-merge-mechanics.md` | 5980 | 7713 |
| `report-integrity.md` | 4232 | 5353 |

These are the six live-longer refs the #1206 dispatch's "refs otherwise in parity" no longer held for;
the planner is live-authoritative, so each copies live→tree (never tree→live). Direction per #791.
`verifying-lane-claims.md` (#1206/#1235) and `already-resolved-vs-live-slice.md` (#1224) remain out of
scope here; no census change; `scripts/architecture_bot.py` untouched (#1236).

## Evidence (measured at PR head)

```
for each of the six: git diff origin/main:<path> <live> = empty
                     git show <head>:<path> | wc -c = 10,125 / 2,590 / 9,020 / 5,700 / 7,713 / 5,353
make check-docs (change-note gate) = exit 0
check_import_roots ratchet: baseline not raised
```

## Acceptance

- [ ] All six `git diff origin/main:<tree> <live>` empty at head.
- [ ] `git show <head>:<tree>` byte counts equal live for each (table above).
- [ ] Note + fragment pass `make check-docs` change-note gate (#1123); `check_import_roots` unraised.
- [ ] One PR for the six-file set; never merged by the implementing lane.
