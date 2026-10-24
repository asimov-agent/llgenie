---
name: issue-triage
description: Decide ONE verdict (implement / refine / close) for the issue in issue.md, from its body and its whole comment thread, and write it to triage.md in the exact shape the next step applies.
---

# issue-triage

You are reviewing one issue of `asimov-agent/llgenie` before anyone implements it. The host
has already written the run's input; your job is the decision, not the change.

## Inputs

- `issue.md` at the repo root. It carries the issue body, its **whole comment thread oldest
  first**, and the decision instruction (`## Decide first, then act`). The thread is the
  issue's real specification: a comment that narrows, reverses or answers the body wins.
- No network and no other file. Do not look for a branch, a PR or an OpenSpec change.

## Output

- `triage.md` at the repo root, and nothing else. Exactly one of these shapes:

```
TRIAGE: implement
```

```
TRIAGE: refine
REFINED:
<an implementable restatement: acceptance criteria explicit, the open question named>
REASON: <one line: what is still undecided>
```

```
TRIAGE: close
EVIDENCE: <what you checked — a merged PR/commit that already does it, the issue that
           supersedes or duplicates it, or why this is not a change this repo can make>
REASON: <one line>
```

## Rules

- **`implement`** — the body plus thread are actionable now. The next leg implements exactly
  the acceptance criteria they agree on and nothing wider.
- **`refine`** — a real decision is still open or the acceptance criteria are missing, so any
  implementation would be a guess. Post nothing yourself; write the `REFINED:` block and stop.
  Never refine because an issue is large or hard.
- **`close`** — the issue no longer makes sense: already implemented, superseded, a duplicate,
  or not a code change this repo can make. `EVIDENCE:` is required and must name what you
  checked; the apply step refuses a close without it. Never close because an issue is hard,
  large or vague — that is `refine`, or a human's call.
- **This is a TRIAGE, not an implementation.** Do not write code, create a branch, push, open
  a PR, or comment on or close the issue yourself. Do not modify any file other than
  `triage.md`.
- If the thread leaves a decision genuinely open, that is `refine` with the open question
  named — not a guess, and not a question to a user who is not there.
