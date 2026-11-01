# Fleet idle continuous-improvement audit contract

**Owned by:** `agents/llgenie-architect/` · versions per lane via #791 · clause folded into issue #1245 (2026-11-02)

This reference is the canonical shape of the **idle continuous-improvement audit** clause that gives each
purely trigger-driven operational lane its own "who conjures the backlog" loop. It is structural, cross-lane
design; per-lane definitions land and evolve through each owning lane's normal issue+PR fold (#791).

## Why it exists
security, documentation-maintainer, ci-pipelines, engine-improver and reviewer are today purely
trigger-driven — they respond to scans/merges that already happen, but have **no loop that produces their
own next issue when the queue is empty**, so a barren lane just idles. The fleet lacked a "who conjures the
backlog" role for these lanes (owner-verified gap).

## Contract shape (owner-approved, non-negotiable)
- **Trigger:** a lane's reactive queue is empty for **N=2 consecutive passes** (no dispatched work, no
  in-flight gate it owns).
- **Action:** the lane runs a defined, **bounded, own-domain** audit; every finding is filed as a refined
  issue in the **six-section shape** (never implemented by the same pass — implementation routes through the
  normal queue).
- **Output artifact (one of two, named):** (a) one or more filed finding issues, or (b) an explicit
  "re-audited at `<sha>`, no findings" record.
- **Bounds:** one-pass scope, no infinite loop; **never overrides real reactive work** — the sweep runs only
  when the queue is empty.
- Filed findings carry the `agent:implement` label so they re-enter the normal queue.

## Per-lane audit definitions
### security
Concluded on-record with @llgenie-security (comment 6551420026 on #1245). See that comment for the verified
wholesale text; summary:
1. **SCAN-COVERAGE** (honesty-clamped): only measurable as "the pinned scanner's reach vs a NAMED baseline
   taxonomy" (scanner's documented capability list, or a class list the fleet fixes). Unclamped "all classes"
   is off-scope.
2. **DEPENDENCY-PIN VALIDITY sweep** (the #1252/#1262 class): uv resolution dry-run against the FROZEN
   reachable-index set (default PyPI + declared extra-index-url, never an unused index) —
   `uv pip compile -q <pin-env>.txt --index-url https://pypi.org/simple --extra-index-url <each reachable> --refresh -o /dev/null`.
   SAT = exit 0 + a lock; UNSAT = exit != 0 naming the pin. Artifact sha-bound (pins + index set + command +
   exit code). Distinct **hard-unsat** vs **unreachable-index** labels.
3. **SCAN-RULE-SET freshness**: pinned scanner/rule-set/DB current or stale baseline.
4. **ADMISSION-GATE coverage**: which gates can/cannot see a vulnerability class reaching main.
Boundaries: findings tagged `security` + `agent:implement`; never implements fixes; never weakens a gate.

### documentation-maintainer
main-versus-docs alignment audit (README/skill sections stale vs current main), skill-freshness (2+ releases
old), change-note coverage.

### ci-pipelines
gate-coverage review (which failures current gates cannot see), workflow robustness (cancelled-mid-flight,
stale-head races — the #1250 class), step-sharpening.

### engine-improver
engine-cell validity (pins resolvable on reachable indexes), serving-parameter drift vs trending-engine sync.

### reviewer
review-process gaps, gate-blind spots that let a bad PR green.

## Versioning note
This is a structural cross-lane contract, so it is versioned under `agents/llgenie-architect/` as the
architecture lane's reference (#791). Per-lane definitions may move to the owning lane's `agents/` tree when
that lane folds them; this reference keeps the consolidated shape while that happens.
