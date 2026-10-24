---
name: issue-dedup
description: Decide whether the two open issues in dedup-in.md describe the SAME defect, and write DUPLICATE or DISTINCT to dedup.md with the evidence (or the reason) the apply step requires.
---

# issue-dedup

The host pairs an older issue with a newer one that looks like a copy. You decide whether
they describe the same defect. A duplicate close retires the COPY only; the older issue is
queued by the host.

## Inputs

- `dedup-in.md` at the repo root: both open issues, the token similarity that paired them,
  and what to answer.
- `AGENTS.md` is already in your context as the repository's durable rules.

## Output

- `dedup.md` at the repo root, and nothing else. Exactly one of these shapes:

```
DUPLICATE: #<older>
EVIDENCE: <the shared behaviour, quoting both titles/bodies>
```

```
DISTINCT:
REASON: <one line: the behaviour the two issues describe differently>
```

## Rules

- **This is a TRIAGE, not an implementation.** Do not write code, do not create a branch, do
  not push, do not open a PR, do not comment on or close an issue yourself, and do not modify
  any file other than `dedup.md`.
- `EVIDENCE:` must name the **shared behaviour**, quoting both titles/bodies. "Similar words"
  is not evidence: two issues can share vocabulary and describe different defects.
- If it is genuinely open whether they are the same, write `DISTINCT:` with the reason — it
  changes nothing, so it is the safe path.
