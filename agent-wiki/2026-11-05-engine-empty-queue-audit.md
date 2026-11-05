# engine-improver lane encodes the empty-queue own-domain audit

## Background (issue #1774, owner requirement 2026-11-01)

The fleet wide-open contract (folded into the planner's SOUL via #1245/#791) requires every
operational lane to encode an **empty-queue own-domain continuous-improvement audit** with named
domains. As measured at `0dcbda8a`, this lane's SOUL had zero encoding of the idle-audit duty
(grep for `empty queue|own-domain|audit|continuous|idle|pin validity|serving drift` → 0). An
operational lane whose reactive queue is empty is never "done" — it must be dispatched onto a bounded
audit of its own domain and produce its own next finding.

## The contract this lane now carries

When this lane's reactive queue is empty, run a bounded, measurable audit of its own domain — the
planner names the engine domain as **engine-cell pin validity** + **serving drift**:

- **pin validity** — silently-unsatisfiable engines/params pins (the #1252/#1262 class) before they
  blow up a future build;
- **serving drift** — serve-capability vs `data/engine-capabilities.json` (an arch serve-capability
  that has lapsed).

Every finding is filed as a refined issue in the six-section shape, implementation routed through the
normal queue — **never this lane's own pass** (this lane implements only its own skill/behaviour). A
clean audit is recorded as `re-audited at <sha>, no findings` and reported on the board. The sweep runs
only when the queue is empty; it never overrides real reactive work.

## What changed

- `agents/llgenie-engine-improver/SOUL.md`: the empty-queue → own-domain audit rule (named domains,
  six-section refined-issue filing, not-own-pass, `re-audited at <sha>, no findings` record).
- `agents/llgenie-engine-improver/skills/llgenie-engine-improver/SKILL.md`: the audit's mechanics rule,
  citing the existing `pin-audit.md` / `registry-contract-following.md` references plus the validation
  commands, and the clean-audit record + report-on-board disposition.

## Acceptance

`make check-docs` + `make lint` green; change-note + fragment per #1123; PR (docs/agents only) closes
#1774.
