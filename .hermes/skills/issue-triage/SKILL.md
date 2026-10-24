---
name: issue-triage
description: Use when an llgenie issue-bot run must decide ONE verdict for an issue — implement, refine or close — and write it to triage.md.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, bots, issue-bot, triage]
---

# Issue triage

The first leg of the issue bot. It decides; it never implements. Everything it needs is already on
disk — the host prepared the input before the agent started.

## Inputs

- `issue.md` at the repo root. It carries the issue, its **whole comment thread** (oldest first),
  and an instruction block with the exact verdict shapes. The thread is the argument: a comment
  that settles the question settles it for you.
- `AGENTS.md` for rules — read the sections the verdict touches (PR lifecycle, tests, Makefile
  wiring), not the whole file.
- `fetched/index.md` when it exists: the text of URLs the issue names, pre-fetched by the host. A
  URL it lists as COULD NOT BE FETCHED is UNKNOWN, not false — do not conclude from it.

## Output

`triage.md` at the repo root, in the shape the instruction block inside `issue.md` prints:

```
TRIAGE: implement
```

```
TRIAGE: refine
REFINED:
<the issue restated so a reviewer could act on it: acceptance criteria that can be ticked off>
REASON: <one line: which decision was open and how the restatement settles it>
```

```
TRIAGE: close
EVIDENCE: <what you checked: the merged PR or commit that already does it, the duplicate's number,
the file that shows the premise is gone — a path:line, a command you ran, a URL from fetched/>
REASON: <one line>
```

## Rules

- **One verdict, and only one.** `implement` when the issue is actionable as written; `refine` when
  the thread leaves a decision open (that is not a guess you get to make, and not a close);
  `close` when the work is already done, is a duplicate, or is not a change this repo can make.
- **A close without `EVIDENCE:` is refused downstream.** "It looks old" is not evidence; name the
  artifact you checked.
- **Do not implement anything.** No code, no branch, no PR, no comment on the issue. The host reads
  `triage.md` and acts; a comment you post yourself will appear twice.
- `implement` means the acceptance criteria are concrete enough that the implementer can start
  without asking anything — if they are not, that is a `refine`.
