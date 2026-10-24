---
name: issue-dedup
description: Use when an llgenie dedup run must decide whether two open issues describe the SAME defect, and write dedup.md.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, issue-dedup, triage]
---

# Issue dedup

The host paired two open issues by token similarity. Similar words are not the same defect — this
leg decides, and the deterministic step after it acts.

## Inputs

- `dedup-in.md` at the repo root: two open issues of this repository (an **older candidate
  canonical** and a **newer candidate copy**), the similarity that paired them, and what to answer.
- The code, when the answer depends on it: a dedup is about the behaviour two issues describe, so
  reading the file they name is evidence, not scope creep.

## Output

`dedup.md` at the repo root:

```
DUPLICATE: #<older>
EVIDENCE:
<the shared behaviour, quoting both titles/bodies; the path:line, command or PR that shows one
fix would settle both>
```

```
DISTINCT:
REASON: <one line: the behaviour that differs, or what would have to be true for them to be one>
```

## Rules

- **A `DUPLICATE:` close retires the COPY only.** The older issue is queued by the host, so name it
  correctly — the older number, never the newer one.
- **No evidence, no duplicate.** "Similar words" is not evidence; quote the shared behaviour and
  name what you checked. The close is refused downstream without an `EVIDENCE:` block.
- **When it is genuinely open, answer `DISTINCT:`.** Closing a real, separate defect as a duplicate
  loses it silently, while a missed duplicate costs one more read.
- **Do nothing else.** No code, no branch, no PR, no comment, no close, no edit outside `dedup.md`.
