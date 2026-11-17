# Proposal: agent-fold-prrebase-2090

## Why

Issue #2881 (filed 2026-11-17, umbrella #2090). Measured 2026-11-17 on main `bb29cc9994`:
`fold-live-profile.py --profile llgenie-pr-merge-conflict` reports 38 same / 1 drifted /
1 live-missing / 13 live-only. The drifted file is `skills/llgenie-pr-rebase/SKILL.md`
(tree `7668f00371b4` vs live `55308ed2c86c`): the live lane book carries **32 lines that exist
nowhere in the tree** (17 pitfall bullets + a 15-line rebase-verdict/salvage block), so a profile
rebuild from the tree silently drops them (#791). A byte-identical fold like #2878's is impossible:
the live SKILL.md is 104,616 chars, over the skill writer's 100,000-char cap, so the fold must be
zero-loss-via-references (the #2118 contract: "move a section into `references/`, never raise the cap").

## What Changes

- Append the 17 live-only pitfall bullets VERBATIM to `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/references/pitfalls.md`, and the 15-line live-only verdict/salvage block VERBATIM to `references/rebase-verification-and-verdict.md` (both currently `same` tree/live, so no duplication risk).
- Add two pointer lines to the tree SKILL.md so the moved rules are loadable, bump its frontmatter `version:` 1.0.0 -> 1.1.0; the tree keeps the `references/fleet-lane-side.md` pointer line the live copy lost.
- No live-side edit in this change: live stays longer (the #2084/#2118 overflow contract; tree->live sync would push an over-cap body into the profile and `sync-agent-profile` refuses it).
- Carry the change note (`agent-wiki/` entry) and `docs/changes.d/` row in the same commit (#1123 gate).

## Impact

- Spec: new capability `prrebase-profile-folding`.
- Code: three files under `agents/llgenie-pr-merge-conflict/**` plus docs fragments; no inference-engine behaviour, no CI semantics, no other lane touched.
- Out of scope (own issues): live-side parity for this lane (#2879) and the 13 live-only profile-root `scripts/` artifacts (#2880).
