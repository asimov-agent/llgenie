# Docs-maintainer: fold live→tree skill drift at main 6cec9d8d

The docs-maintainer own-domain audit (tracked #1645) surfaced live→tree profile drift on this lane's
own skill for `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/`. Re-measured
at `origin/main` `6cec9d8d` (finding #2019 filed at `58e10771`; `main` moved via the #2014
architecture refresh, which touched `docs/ARCHITECTURE.md` only — the skill drift is unchanged):

- `SKILL.md` tree `version: 1.0.22` (101849 b) vs live `version: 1.0.23` (99414 b) — the live rewrite
  restructures `own-domain-audit` / lint-and-gates pointers into references and drops inline prose the
  tree still carries. Fold copies the LIVE file's inline pointers verbatim.
- 6 ref files live-longer than tree (live mtimes post-date the last fold #1801, merged 2026-11-05):
  `agents-soul-doc-changes.md` (10343 → 16018), `base-race-rebase-and-metadata.md` (2871 → 3902),
  `dispatch-race-verification.md` (6037 → 7887), `lint-and-gates.md` (1607 → 4702),
  `merged-ci-verification.md` (2455 → 3848), `own-domain-audit.md` (4304 → 10901).
- 4 refs live-only (never committed, `git log --all` empty): `acceptance-writeback-heading.md`
  (2236 b), `acceptance-writeback.md` (3983 b), `acceptance-writeback-seam.md` (2814 b),
  `landed-change-verification.md` (2988 b). This brings live refs 23 = tree 23.

Per #791/#1060 a live→tree fold is a change under `agents/<profile>/` and lands as the owning lane's
issue+PR (finding #2019 → this PR). The fix folds all 10 files byte-identically (`cmp` per file at the
head) and never runs a write-mode `sync-agent-profile`, which is one-way tree→live and would truncate
the richer live files (#791 trap). After merge: `make sync-agent-profile
PROFILE=llgenie-documentation-maintainer CHECK=1` must report `OK: N file(s) match byte for byte,
rc=0`.

Scope carefully bounded: only this lane's own skill directory. The lane's `SOUL.md` also differs but
in the OPPOSITE direction (tree 20044 b has 2 fleet rules from #1891/#1889 that this live profile
predates) — that is tree→live provisioning drift, not live→tree, and is NOT part of this fold (folding
live would shrink the tree). It is resolved by a normal tree→live sync after merge, not by this PR.
