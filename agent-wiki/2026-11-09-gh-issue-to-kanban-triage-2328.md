# Versioning the gh-issue-to-kanban-triage reference (issue #2328)

## What changed

The planner's triage-to-kanban procedure was **live-only**: `$HOME/.hermes/profiles/llgenie-planner/skills/llgenie-bot-orchestration/references/gh-issue-to-kanban-triage.md`
existed on the host but the repository tree did not carry it, so a fresh worktree or a
profile re-sync (`make check-agent-profiles` reds a live-only reference) silently dropped it and
the next planner re-derived the `--title`-doesn't-exist / dedupe / archive-not-delete pitfalls
from scratch.

1. Copied the live reference **verbatim** into
   `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/gh-issue-to-kanban-triage.md`
   (`119 lines / 6,353 B`; live→tree md5 `295daa6b…` byte-identical). The reference documents the
   full procedure: measure candidates → route by the #2073/#2270 ownership map → create the card
   (positional `--title`, `--json` id read-back) → dedupe/verify (one live card per issue). It also
   covers BOTH triage directions — no-PR `agent:implement` issues AND each open PR's closing issue
   carded as a read-only mirror.
2. Added the one-line anchor to the skill's `SKILL.md` in the kanban-machinery bullet block
   (the tree lacks the `ci-workflow-trigger-taxonomy` anchor that live's copy sits near — that
   reference is part of the wider live-only drift, issue #2328 scopes this to the triage reference
   only): `GH issues→kanban cards ("load N to triage"), both directions … : references/gh-issue-to-kanban-triage.md`.

## Verification (what this change proves)

- Reference present in the tree and **byte-identical to live** (md5 `295daa6b…` both sides).
- `SKILL.md` links it (the anchor greps 1). Tree previously referenced it 0 times.
- `make check-docs` / `lint` / `check-wiring` green on the branch at head.
- Change-note trio present (this note + `docs/changes.d/…2328.md` + `CHANGES.md` index row).

## Decisions / scope

- This is a **docs-only fold of one live reference** under `agents/llgenie-planner/`. It does not
  restructure unrelated skill files; the 34 other live-only planner references are a separate drift
  (each their own fold vehicle, #791 class), not this issue.
- The issue's UPDATE section (LOAD-20-TO-TRIAGE tick-prompt step 6d) is **out of scope here**: it is
  a tick-cron behavior change under `prompts/`, gated by the #2136 check-tick-prompt drift gate, and
  belongs to the planner/implementer lane — not a docs-only reference fold.

## Issue / PR

Implements #2328. Docs-only. Never merged by hand, never armed (#1088).
