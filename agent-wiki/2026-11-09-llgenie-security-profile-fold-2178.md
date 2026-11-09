# llgenie-security — #2178: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2178
- **Branch:** `llgenie-security/2178-profile-fold` (from `origin/main` `54ff1145`)
- **PR:** the ready-for-review PR closing #2178 (base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-security CHECK=1` reported `4 of 14 file(s) differ` with
**2 of them would SHRINK the live profile** — the tree copies of
`skills/security-scan-ops/SKILL.md` (61,700 vs live 72,528 b) and
`skills/security-scan-ops/references/agent-soul-versioning.md` (14,260 vs live 17,056 b) were the
truncated side, so a blind tree→live sync would have destroyed live behaviour (#2090-class). Direction
for this lane is therefore **live→tree**: the live profile at
`~/.hermes/profiles/llgenie-security/` is the source of truth, the repo copy the destination.

## What this PR folds

- **`skills/security-scan-ops/SKILL.md`** — interleaved drift (103 live-only lines + 6 tree-only,
  including the #1791-AC3 failing-job-log pointer paragraph). Resolution is a **union**: the live copy
  (newer, longer) is the base and the tree-only pointer paragraph (`references/read-the-failing-job-log-pointer.md`)
  is merged back, so neither side loses lines. Two prose examples that would red
  `skill-reference-missing` were reworded to `references/<canonical-pointer>.md` / `references/<X>.md`,
  per the lane's own #1849/#1855 rule (canonical cross-lane path lives in the pointer FILE body, a
  `references/` file's content is not scanned).
- **`skills/security-scan-ops/references/agent-soul-versioning.md`** — live strict superset (29
  live-only, 0 tree-only); copied live→tree byte-identically.
- **`skills/security-scan-ops/references/read-the-failing-job-log-pointer.md`** — **tree kept**: live
  entirely lacks it, so the sync adds rather than shrinks.
- **`skills/security-scan-ops/references/security-issue-review.md`** — **tree kept** (10,709 vs live
  10,695 b; only `$HOME` against absolute-path spelling, semantically identical).
- **`skills/security-scan-ops/references/ci-red-read-the-job-log.md`** — **live-only file** folded into
  the tree for the first time (absent-from-tree class, #1060).

After the fold every tracked file is tree ≥ live, so a rebuild materialising the tree cannot downgrade
the lane. `make sync-agent-profile PROFILE=llgenie-security CHECK=1` reports `0 of 14 file(s) differ`
after the re-sync.

## Deliberately NOT folded

The wider live-only `.hermes/skills` set (transverse skill suites like github/code-review,
dogfood, productivity, research) is not this lane's versioned surface; per the issue, profile-only
skills are drift to be folded or retired separately, and provisioning has no delete path (#2165).
