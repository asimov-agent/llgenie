# The 100,000-character cap the skill writer enforces, and the four skills that were over it (issue #2084)

`skill_manage` refuses any write to a `SKILL.md` above **100,000 characters**, and the refusal rolls
back **every** skill touched in that batch. A lane whose skill sits over the cap therefore cannot
record a single lesson: it keeps running, keeps learning, and silently loses each correction. Nothing
in CI measured this, so the only symptom was a lane that stopped improving.

## The measurement

At `origin/main` when this was written, counted in characters (the unit the tool uses — its message
reads `SKILL.md content is N characters (limit: 100000)`):

```
101,586  OVER  agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md
103,203  OVER  agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/SKILL.md
106,407  OVER  agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md
103,927  OVER  agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md
```

The issue named one of these. The gate found three more, which is the argument for measuring every
skill rather than patching the one that happened to be reported. Bytes and characters diverge on a
file with non-ASCII text — `llgenie-tester`'s skill is 99,820 characters but 100,442 bytes — so a
byte-based rule would have reddened a file the tool saves happily. The gate counts characters.

## The remedy the gate now names

Overflow does not come out of the file; it moves. Whole sections go into
`references/<topic>.md` and `SKILL.md` keeps a one-line pointer. That is lossless by construction:
every line of the old file still exists, just in a file the agent reads when the pointer sends it
there. The finding says so explicitly, because a lane told only the character count learns nothing
about what to do and reaches for deletion — which is how a rule disappears.

## Why the planner copy mattered beyond its own size

The tree copy was 102,039 bytes while the live profile had already been corrected to 98,968 with four
support references carrying the overflow — and **none of the four existed in the tree**. The
documented one-way `make sync-agent-profile PROFILE=llgenie-planner` would have replaced the corrected
live copy with the over-limit tree copy and dropped all four references, reverting the night's work
and re-orphaning the same lessons.

Copying the live file over the tree is not the fix either: measured, the live copy is 99,575 bytes and
the tree held **81 distinct lines the live copy lacks**. The fix is tree-based — take the tree as the
base, move its `## When to Use` into `references/when-to-use-and-pass-shape.md`, and add the four
references the tree never had. Verified: 715 tree lines, **LOST 0**.

## What the gate does

`scripts/check_agent_skills.py` gained a `skill-over-char-limit` finding over
`agents/*/skills/*/SKILL.md`, reached through `make check-agent-skills`, and wired **twice**: into
`make ci-unit` (the `linux / unit` row in `pipeline.yml`) and into **`guard`**, the always-running job
in `ci.yml`. It names the file, the character count, the overflow, and the remedy.

**Why the `guard` wiring matters more than the first one.** `linux` declares
`needs: [ci-images, guard]`, so any guard red **skips the whole matrix** — and a job that never ran
looks exactly like a job that passed when you read the run from outside. Measured at head `614c6a62`:
the guard red (this issue's own item-3 designed hold) left `linux` skipped, so a gate wired only into
`ci-unit` **executed zero times**. Scope had selected the row — `job=linux/unit run — class
scripts+tests+data+skills+containers+workflows` — and it still did not run. A gate a red elsewhere
can skip is not a gate, so `check-agent-skills` now also runs in `guard`; it is seconds of work (read
each `SKILL.md`, compare lengths), and `check-wiring` counts the new call (131 make targets, was 130).
An unreadable skill is its own finding (`skill-size-unreadable`) rather than a silent skip: a file
whose length cannot be measured is not a file that passed.

Proven by sabotage on a real skill — padded to 121,461 characters the gate went RED naming
`agents/llgenie-product-manager/skills/llgenie-product-manager/SKILL.md` and `21,461 over`; with the
padding removed it went GREEN. The unit tests drive the real script against fixture trees for the
failure shape, the remedy text, the exact-at-limit boundary, and the character-vs-byte distinction.
