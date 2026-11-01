# Planner continuous-improvement contract — empty-queue lanes run their own-domain audit

The planner's live SOUL.md and `skills/llgenie-bot-orchestration`/SKILL.md gained a clause on 2026-11-01: an operational lane whose reactive queue is empty is never parked "idle — it is dispatched onto a bounded, measurable own-domain audit that produces its own next finding. This folds that live behavior into the tree byte-for-byte.

## What changed

- **SOUL.md**: a new "An empty queue is not an idle excuse" clause under Standing behaviour — an operational lane (security, documentation-maintainer, ci-pipelines-maintainer, engine-improver, reviewer, rebase-conflicts) with an empty queue is dispatched onto its own-domain continuous-improvement audit, not parked. The clause also carries the trailing-newline fix on the final "This lane's rules" line.
- **SKILL.md** (`llgenie-bot-orchestration`): the matching "An EMPTY queue is still not 'done'" clause in the orchestration pass, plus the already-live #1245 per-lane audit definitions it references. Per-lane audit scopes are named (security: scan-coverage, dependency-pin validity; documentation: main-versus-docs alignment, skill-freshness; ci-pipelines: gate-coverage, workflow robustness; engine: pin validity + serving drift; reviewer: review-process gaps). Every finding is filed as a refined six-section issue routing through the normal queue, never the audit lane's own pass; a clean audit is recorded `re-audited at <sha>, no findings`, and the sweep runs only when the queue is empty, never overriding real reactive work.
- **SKILL.md** (same): the loop-escape clause — a lane answering the SAME correction twice is a signal, not a reason to re-ack (stop acking a repeated correction, anchor agreed facts on the vehicle, re-measure the canonical tip each pass; base and parent are distinct, and a rebase onto the PR's current parent is a no-op — #1015 rebase only on real conflict).

## Why

Structurally, this is the same drift the fleet has been versioning all night: live behavior ahead of the tree, folded via issue+PR under #791. The files were appraised at 01:11Z, settled (identical signature across six polls), and byte-copy verified.

## Trails

- Structuring issue: #1245.
- This versioning fold: #1273.
