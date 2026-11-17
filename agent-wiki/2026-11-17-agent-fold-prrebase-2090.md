# 2026-11-17 — agent-fold-prrebase-2090: zero-loss fold of the pr-rebase lane's live-only rules

Issue: #2881 (umbrella #2090; side issues #2879 live parity, #2880 live scripts/ artifacts).

## What was verified

- Census at `origin/main`: `scripts/fold-live-profile.py --profile llgenie-pr-merge-conflict` →
  `38 same / 1 drifted / 1 live-missing / 13 live-only`; the drifted file is
  `skills/llgenie-pr-rebase/SKILL.md` (live `55308ed2c86c`, 104,616 chars, over the skill writer's
  100,000-char cap; live-only content: 17 pitfall bullets at live lines 358-374 and a 15-line
  Check-11/verdict/salvage block at live lines 376-390).
- Byte-identical fold (#2878's pattern) was impossible: appending 32 long lines (~26k chars) to an
  85k-char tree SKILL.md passes the tree gate but the same file synced live stays unpatchable, and
  the live side is 104,616 chars — the #2118 contract applies: "move a section into `references/`,
  never raise the cap."
- Fold applied live→tree only: 17 bullets appended verbatim to `references/pitfalls.md`, the
  15-line block appended verbatim to `references/rebase-verification-and-verdict.md`, two pointer
  sentences added to SKILL.md under a "Live-folded rules (issue #2881)" section, frontmatter version
  1.0.0 → 1.1.0, tree-only `references/fleet-lane-side.md` pointer preserved.
- Zero-loss proof replayed after the fold: the 33 live-only diff lines (32 measured at `bb29cc9994`
  + 1 uncovered by #2853's slim — all of them) each appear byte-identically in the tree union of
  SKILL.md + the three references; 0 missing. Live profile untouched (sha `55308ed2c86c` before and
  after).

## Decisions

- Live stays longer (over-cap) on purpose: `sync-agent-profile` would push a >100k body into the
  profile; the live-side reconciliation is #2879, the live `scripts/` runtime artifacts census is
  #2880 — out of this change per the one-objective-per-issue rule.
- The two target references were `same` tree/live before the append, so the fold cannot duplicate a
  rule that already exists elsewhere in the lane.

## Status

OpenSpec change `agent-fold-prrebase-2090` validated; fold shipped in one commit closing #2881.
