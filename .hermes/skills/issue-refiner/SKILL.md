---
name: issue-refiner
description: Use when an llgenie refiner run must review ONE open issue and write its verdict to refine.md — restate it, or say it is already clear.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, issue-refiner, review]
---

# Issue refiner

The refiner spends the implementer's spare capacity on the *review* of a not-yet-implemented issue.
It is a review, never an implementation: the only thing it writes is its verdict.

## Inputs

- `refine-in.md` at the repo root: an issue, its **whole comment thread** (oldest first), and the
  review instruction with the exact verdict shapes.
- `fetched/index.md`: the text of every URL the issue or its thread names, pre-fetched by the host
  before you started. This is what the outside world actually says — use it instead of guessing. A
  URL it lists as COULD NOT BE FETCHED is UNKNOWN, not false.
- `AGENTS.md` for the repository's rules.

## Output

`refine.md` at the repo root:

```
REFINE: refined
RESTATED:
<the issue restated so a reviewer could tick off each acceptance criterion>
REASON: <one line: what was missing>
```

```
REFINE: already-clear
REASON: <one line: why nothing needs adding>
```

## Rules

- **`refined` requires `RESTATED:`.** A restatement the reviewer cannot act on is worse than no
  comment: give behaviour, the command or interface, and what "done" looks like.
- **`already-clear` is a real answer**, not a way out — say what makes the issue actionable already.
- **A decision the thread leaves open is a question in the restatement, not a decision you make.**
  Name the options and what each implies; the owner picks.
- **Change nothing else.** No code, no branch, no PR, no comment on the issue, no edit outside
  `refine.md`. The host posts the comment and applies the `agent:refined` label.
