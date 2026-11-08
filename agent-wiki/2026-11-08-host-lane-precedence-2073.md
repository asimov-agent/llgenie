# llgenie-bot-orchestration: host-lane working takes precedence over CI machinery (#2073)

The planner's own instruction set gains the owner's precedence rule. Measured 2026-11-08: six PRs
were stale-base (`merge-base(main)=d7f57cfa` against main `88ead5b9`), and the planner spent
cycles dispatching `rebase-bot.yml` (`42438486613`, `rebased: 0`) and diagnosing
`scripts/rebase_bot_sweep.py` locally before dispatching `@llgenie-pr-merge-conflict` — the lane
that exists to do exactly that. The owner corrected this explicitly (owner directive 2026-11-08):
*"your own behaviour for working with your bots should always take precedence on the host.. the
CI is just the CI really"*.

## What was verified

- New `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/host-lane-precedence.md`
  states that **host-lane working always takes precedence on the host**: a pass reaches for the
  owning host lane first; CI is only the reporter, never the repair target (AC1).
- It carries the **host-lane ownership map** and the rule that a declined automation job routes to
  the owning host lane, not planner-side repair (AC2).
- It names the precedent that a pass finding an in-repo bot declining a PR dispatches the owning
  host lane **before** re-dispatching the in-repo bot (AC3).
- It states the **two-trail rule**: one issue in the owning code lane for the defect (e.g. #2071
  owns the `rebase_bot_sweep.py` blindness), and one host-lane dispatch plus an on-PR anchor for
  the unblock — never folded (AC4).
- It restates that the planner never authors a branch, commit or code change on this path (AC5).
- The change is **versioned as a PR under `agents/llgenie-planner/`** (AC6, per #791) — reference +
  SKILL.md pointer only, no private host edit.

## Decisions

- Lane ownership map mirrors section **2b** of the orchestration SKILL.md, so the new precedence
  rule is consistent with the existing route-to-owner table rather than adding a competing one.
- This is a behaviour-versioning reference change, matching the #1877/#1891 pattern: reference
  file + one-line SKILL.md pointer + change-note trio. No scripts, tests or workflows were edited
  (#1088). No OpenSpec change is owed — the change is documentation of an agent's own dispatch
  rules inside `agents/llgenie-planner/`, not a repo behaviour gate (consistent with the prior
  `docs(planner)` reference-versioning PRs).

## Status

Reference, pointer, wiki note, `docs/changes.d` fragment and `CHANGES.md` index row all present.
The planner reads the rule from `references/host-lane-precedence.md` at dispatch time.
