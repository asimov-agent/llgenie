# LLGenie Pipeline Maintainer: empty-queue own-domain audit clause (owner 2026-11-01, #1245)

Folds the continuous-improvement contract's per-lane clause for this lane (structuring issue #1245, architect
per-lane spec comment 6551533999; pattern set by planner's versioning issue #1273). This lane is trigger-driven
and had no loop that produced its own next issue when the queue was empty — a barren lane simply idled.

## What changed (fold live→tree, byte-identical)

- `agents/llgenie-ci-pipelines-maintainer/SOUL.md` — new bullet under "This lane's rules (kept outside the
  fleet block)": an empty reactive queue for N=2 consecutive passes is one bounded own-domain audit, not an
  idle pass. This lane's audit definition: **gate-coverage review** (which failures current gates cannot see),
  **workflow robustness** (cancelled-mid-flight, stale-head races — the #1250 class), **step-sharpening**.
  Findings filed as six-section `agent:implement` issues (never implemented by the same pass); otherwise
  `re-audited at <sha>, no findings`. One-pass, never overrides reactive work.
- `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/SKILL.md` — matching
  "Empty-queue own-domain audit (2026-11-01, #1245)" section with the same clause.

Live profile was authored first (the authoritative copy per owner #1245/#1257); the tree copy is a live-ahead
byte fold (SOUL md5 `ae3e0b0e», SKILL md5 `083e5cc5» == live), not a truncation.

## Verification

- Tree `SOUL.md` + `SKILL.md` byte-identical to live (md5 match after authoring).
- `check_docs.py check` rc=0 on this head (change-note pair ships in the same PR, #1123).
- Merge owner-gated (#1088); arming per #964 (green head only).
