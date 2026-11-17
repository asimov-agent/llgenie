## 2026-11-17 — issse-implementer bulk-migration skill fold live→tree (issue #2877, PR #2878)

Resolved the lane's live-only shadow `skills/bulk-mechanical-migration/` (1 file, 9327 b, live
`2c5f8bb26a02…`) WITHOUT a second tree copy: the same live profile also carries the richer category
copy `skills/software-development/bulk-mechanical-migration/SKILL.md` (9807 b, `9e379c86…`, includes
the `Role artifact (2026-11-01)` section), byte-identical to the tree copy versioned since #2238 —
the shadow's identity was already versioned. Landing the flat copy was measured to redden
`tests/test_provision_agent_profiles.py::test_no_lane_tree_carries_the_same_skill_identity_twice`
(the #2836 collision the fold itself created at `f146ce1926`), so the branch removes it: Hermes
unions a lane's whole skills tree into one store, and one identity may appear only once. The lane's
tree lands the SOUL edit (live→tree, byte-identical) only. Direction live→tree throughout; no
live-side edit, no writing sync (the #2327 identity-proof shape).

Measured on `origin/main bb29cc9994f479e2900863b3c9444ec5d2a58566` from a detached worktree: the #791
gate carried 9 findings; this lane contributed exactly 1 (`absent-from-tree`), and the lane's own
census was already clean (79 same / 0 drifted / 0 live-missing / 0 live-only / 0 mid-write) — earlier
folds #2238/#2327 versioned the rest. The surviving tree copy carries `version: 1.0.0`.

Why it was worth doing: the fixture `tests/fixtures/host-bot-capabilities.json` already pins
`bulk-mechanical-migration` as this lane's `lane_skill` (line 85) — the versioned copy satisfies the
pin, and this change makes the census unambiguous by refusing the shadow's second copy instead of
adding one. #2090 AC5 (the lane's fold leaves the gate clean for it) is satisfied by this lane's zero
remaining rows.

Verified at the head: `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` rc=0
(byte-for-byte, check-only); `make -s check-agent-profiles` prints no FAIL row naming
`llgenie-issse-implementer`; `make -s check-docs` rc=0.
