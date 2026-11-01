# agents(planner): fold unversioned live drift — 4 live-longer + 4 absent-from-tree planner files (#1390)

The planner's live profile carries 8 files whose committed tree copies are neither current nor
complete — `scripts/check_agent_profiles.py` from a clean worktree at origin/main `f41685f3`
reports 12 planner lines: 4 `live-longer` files where live grew beyond the tree prefix, and 4
`absent-from-tree` files that exist only in the live profile.

**live-longer (live > tree; tree lacks the tail):**
- `skills/github-issue-triage/SKILL.md` — tree 29,739 b → live 30,578 b (1 new line)
- `skills/llgenie-bot-orchestration/SKILL.md` — tree 112,364 b → live 112,550 b (1 new line)
- `references/stalled-lane-and-dispatch-delivery.md` — tree 26,728 b → live 28,117 b (15 new lines)
- `references/verifying-lane-claims.md` — tree 87,753 b → live 90,446 b (10 new lines)

**absent-from-tree (live-only, byte-identical folded in):**
- `skills/github-issue-triage/templates/implementer-handoff.md` (2,235 b)
- `skills/llgenie-bot-orchestration/references/filing-refined-issue.md` (3,620 b)
- `references/merged-over-red-gate.md` (3,248 b)
- `references/profile-fold-verification.md` (2,731 b)

Each is copied live → tree verbatim and `cmp` byte-identical at the fold head. The shrinking
seed guard was the concern: a `make sync-agent-profile` is one-way tree → live, so running it
over the live-longer files would REPLACE the larger live rulebook with the smaller tree prefix
and silently delete the newer live lines (#791) — folding live → tree preserves them.

**Bundle-wide proof (measured at the fold head):** all 8 target files `cmp` byte-identical
live vs tree; `scripts/check_agent_profiles.py` reports **ZERO** `llgenie-planner` lines from a
clean worktree at the fold head (bundle standard #1273 — whole `agents/llgenie-planner/skills/`
including references/ + templates/ is tree==live). Fold landed at base `f41685f3` then rebased
onto `dcd91255` (the #1388 trailing-newline fix that landed on main mid-fold); re-verified
byte-identity of all 8 against live at the rebased head.

**Gates:** `make -s check-docs` rc 0 (census gate OK), `lint` rc 0, at the committed head.
Change-note pair ships in this PR (#1123).

`AGENTS:` preflight — base = origin/main `f41685f3` (15:41Z fetch; small self-contained repo,
make-target verification, ghost-gate discipline honoured).

