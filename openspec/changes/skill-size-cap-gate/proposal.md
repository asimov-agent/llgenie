# Skill-size cap gate: an over-limit SKILL.md is a red gate that names its own fix

## Why

A Hermes skill body over 100,000 characters is **un-patchable**: `skill_manage` refuses the save and rolls
the whole batch back. Measured on `origin/main` `c3f3b2ac`, four tree skills were past it —
`llgenie-bot-orchestration` 101,977 characters, `llgenie-pipeline-maintenance` 103,203,
`llgenie-engine-improver` 106,407, `llgenie-pr-rebase` 103,927 — so their versioned rulebooks could only
drift further from live behaviour, and the tree→live sync would have written an un-patchable body into a
live profile. Nothing in the repository refused this state: the copies are valid markdown and every gate
was green.

## What Changes

- `scripts/check_agent_profiles.py` gains a `skill-size` finding: any `agents/*/skills/*/SKILL.md` past
  `SKILL_MAX_CHARS = 100_000` fails `make check-agent-profiles` (inside `make ci-unit`), naming the file,
  the character overflow, the byte count, and the **remedy** — move sections into `references/` linked
  from the body, never raise the cap.
- The same gate refuses an over-limit exemption record that is unreadable or carries no
  `reason`/`issue`/`date`, and reports a **stale** exemption once its file is back under the cap (or gone),
  so the record cannot rot into a silent allowance.
- `tests/fixtures/skill-size-exceptions.json` records the three pre-existing over-limit skills as dated
  decisions naming their own slimming issue (#2114), so the gate can be ON while they are worked.
- `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` is brought under the cap
  tree-based and zero-loss (its `## When to Use` section moves verbatim into
  `references/when-to-use-and-pass-shape.md`), and the five references it and the issue name are committed
  and linked from the pointer block.
