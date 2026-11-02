# #1398 — dedup the canonical 'never push' rule in the planner SOUL

Change date: 2026-11-02 · Surface: `agents/llgenie-planner/SOUL.md` (agents profile text) · Gate: #1123 change→note

## What changed

`agents/llgenie-planner/SOUL.md` carried the canonical fleet rule **"Never push to a branch you were not
dispatched for"** twice:

- **line 130** — a bolded restatement in the lane-rules section (draft PR ≠ licence to edit another
  lane's files; commit author is not cosmetic, `check-pr-authors` #840; a label is board state that
  belongs to the planner; report with a one-line reason and a one-line unblock condition), and
- **line 138** — the fleet Standing-rules bullet ("another lane's PR is read-only; propose a patch as a
  comment").

The `_duplicate_rule_debts` pass in `scripts/check_agent_profiles.py` counted both (it matches the bolded
`**Title.**` form) and emitted a non-blocking note each run: *"states 'Never push to a branch you were not
dispatched for' more than once (duplicate canonical rule — one bullet, one place, #972)"*.

## The dedup

The line-130 restatement is re-worded as lane prose ("The never-push rule (fleet Standing rules below) is
operational here, not just stated: …") that keeps every operational detail (draft-PR-≠-licence, commit
author not cosmetic / #840, label board-state, one-line report + one-line unblock), without re-stating
the bolded canonical title. The line-138 fleet bullet remains the single bolded canonical occurrence.

**No information loss** — both the line-130 prose meaning and the line-135/138 bullet meaning ("another
lane's PR is read-only; propose a patch as a comment") survive in the one remaining occurrence's context.

**No `fleet-block-drift`** — the verbatim `## Standing rules (fleet, learned 2026-10-28)` block is
byte-identical to `agents/standing-rules.md` (`_fleet_findings` requires it).

## Verified at the commit head

- `_duplicate_rule_debts` bolded-count = **1** (only the fleet bullet) → the #972 duplicate-note stops
  firing for `llgenie-planner`.
- CI-parity `check-agent-profiles` (no live profiles dir, as on runners) → **OK, LIVE RULEBOOKS NOT
  COMPARED** (the host `~/.hermes/profiles` drift shown locally is pre-existing across many lanes and
  does not exist on CI runners).
- `make check-docs` → **ok** (changes-index 433 fragments, census at ancestor `bb11bb1f`, 2458 tracked);
  `changes_index.check = []`.

Closes #1398. One vehicle. Fleet/planner confirmation on the owner-granted SOUL write (2026-11-02).
