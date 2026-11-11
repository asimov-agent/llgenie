# 2026-11-09: versioned the 38 live-only earned skill lessons (issue #2062)

The ci-pipelines-maintainer lane had accumulated **38 named lessons** in its private live profile
(`skills/llgenie-pipeline-maintenance/SKILL.md`), absent from the canonical tree and from `git` —
one `make sync-agent-profile` away from loss (issue #2062). They were preserved to
`backups/soul-skill-reload-20261108T015719Z/` on the 2026-11-08 reload (never deleted, per the
no-prune rule). This PR folds them into the versioned tree.

## Fold target

- 30 rules survive and now live verbatim in `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/live-only-skill-lessons.md`, pointed to by one line at the top of the canonical `SKILL.md` (the repo's existing pointer style).
- 7 rules are **superseded** — the canonical `SKILL.md` / references already carry the identical lesson, so re-adding would duplicate (this is the `429-line-only canonical set` the issue told us not to re-add into a private copy).

## Kept (30) → `references/live-only-skill-lessons.md`

1. A `workflow_run` consumer (ci-verdict) must judge a run whose PR is ALREADY MERGED as a post-merge straggler → neutral, never red (#1741)
2. A docker-driver builder can READ a registry cache but cannot EXPORT one — buildx cache-WRITE must stay on the active docker-container builder
3. A change to `scripts/engine_image.py` (any behavioural pipeline script) trips the change-note gate (#1123)
4. `check-pr-openspec-change` has an OR-branch — an `openspec/changes/<name>/` dir clears it
5. An owner "rebase onto the new main tip <sha>" directive does NOT clear a base-independent gate red
6. A NEW acceptance/issue-state gate can RED THE PR THAT INTRODUCES IT (chicken-and-egg)
7. Verify a landed `acceptance_writeback` by RE-RUNNING the guard at the LIVE head
8. A NEW PR-body-FORM gate placed AFTER an issue-state gate is UN-PROVEN on the wire — order the body-form gate FIRST
9. A section-reading gate that prints `OK` on an EMPTY section has proven nothing
10. A deferred criterion clears `check-pr-acceptance` through the gate's OWN `## Not covered` escape
11. A NEW user-facing make target (with a `##` help line) must also be NAMED in `docs/BOTS.md`
12. Before opening a pipeline-fix PR, sweep the PRs on the target file (duplicate-vehicle + closing keyword)
13. A body-only CI fix needs TWO reruns (the CI run AND the ci-scope run read the live body independently)
14. A merged PR re-reported as red is a phantom — its body, head and branch are frozen
15. `check-pr-closing`/`bot_preflight`/`check_pr_hygiene` stdlib-only host gates (in the container they die `fatal: not a git repository`)
16. Do NOT paste the `make bot-preflight` line from a fork-origin worktree — cite the CANONICAL sha
17. A repeated job NAME (`guard`) does not identify which job owns a gate — run the gate itself
18. The host's file-write path drops the trailing newline — run `python3 scripts/lint_linefeeds.py` before commit
19. When the host's stdout channel goes DEAD, the exit code is the only truth (dead-channel protocol)
20. A peer-quoted SPACED-AGENTS red is a STALE-HEAD red once the branch is force-pushed
21. A `linux/unit` red with a GREEN pytest summary is a HYGIENE gate (usually `check-pr-base`), not a test
22. After a `--force-with-lease` push the pulls API `head`/`base` LAG the wire — use `gh pr checks`
23. A `pending`/0-jobs/frozen `updated_at` trigger run on a REBASED head is the concurrency-QUEUED signature
24. A `pull_request`-only producer exposes NO manual dispatch — a re-dispatch request is answered with the live witness
25. A `ci-verdict`-style `workflow_run` wrapper's `head_sha` is the DEFAULT BRANCH, never the run it consumed
26. A section-reading gate's found-headings canary must red on a non-canonical acceptance heading
27. A gate that reads the issue body live leaves a stored pre-writeback FAILURE that is not a defect — re-run it, never re-fix
28. A job-count read from `gh run view --json jobs` must count the `jobs[]` ARRAY, never a `total_count` key
29. A downstream `workflow_run` CONSUMER keeps its own frozen FAILURE until the re-run upstream run COMPLETES
30. Confirmed again (#1862): a "verdict red at the merged main tip" dispatch resolves to genuine PR guard-failure reds — no false-red to fix

## Superseded (7) → already in canonical SKILL.md (do not re-add)

1. **Scope is the MONITOR loop** — canonical `\\## When to Use` (the same paragraph)
2. **Scope is MONITOR and ROUTE, never rebase** — canonical `\\## When to Use` (same paragraph + owner instruction)
3. **git add -A commits every OTHER lane's file** — canonical `\\## PR discipline` ¶
4. **One worktree per PR — before the first edit, `git rev-parse --abbrev-ref HEAD`** — canonical `\\## PR discipline`
5. **The remote NAMES on this host are not stable** — canonical `\\## The repo, and the remote that is the truth`
6. **This host has TWO main repositories** — canonical `\\## The repo…` (TWO main repositories paragraph)
7. **Git-based host gates stdlib-only (container dies `fatal: not a git repository`)** — canonical `\\## Pitfalls` (the `pytest`/worktree `.git` paragraph)

## Reference-layer drift inventoried (NOT silently truncated)

The same reload found references **larger live than canonical** — the tree carried a *truncated seed*
for these, so a blanket `make sync-agent-profile` would have deleted live behaviour. This PR folds the
fuller live copy into the tree for every oversize shared reference (17 files), and lists the rest.

Folded live→tree (tree is now a superset, sync is safe — `sub-O(1)` per file):

| reference | tree (was) → now live-sized |
|---|---|
| `agent-profiles.md` | 9,459 B |
| `auto-merge-identity.md` | 10,078 B |
| `change-note-gate.md` | 20,296 B |
| `ci-job-selection.md` | 17,572 B |
| `ci-verdict-rejudge-and-expiry.md` | 3,428 B |
| `diagnosing-cancelled-runs.md` | 16,097 B |
| `engine-build-cuda-cdi.md` | 4,757 B |
| `hermetic-run-and-census-quirks.md` | 4,424 B |
| `monitoring-check-rollups.md` | 17,899 B |
| `pr-issue-linking-and-force-push.md` | 7,315 B |
| `repo-artifact-conventions.md` | 9,215 B |
| `runner-queue-diagnosis.md` | 13,996 B |
| `shared-branch-coordination.md` | 4,255 B |
| `verification.md` | 29,994 B |
| `verifying-a-dispatch-premise.md` | 8,007 B |
| `verifying-agent-tree-parity.md` | 5,229 B |
| `verifying-planner-claims.md` | 28,505 B |

References that exist **only in the live profile** (no tree counterpart) remain a separate documented
drift class — `check_agent_profiles.py` flags each as `absent-from-tree` (issue #1060); they are not
part of this issue's fold and are not silently deleted by sync (sync has no delete path).

## Proof

- Every kept rule is present in the tree: `grep -Fc` for each lead phrase into
  `references/live-only-skill-lessons.md` → ≥ 1 (see PR body `Verification` table).
- `make sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer` runs and the live `SKILL.md`
  sha256 equals the repo blob's (both recorded in the PR).
- Backup `backups/soul-skill-reload-20261108T015719Z/` left in place.

## Sync byte-equality proof (AC5)

`make sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer` ran clean (no shrink refusal) and the
live `SKILL.md` now equals the repo blob byte for byte:

- repo `SKILL.md` sha256: `7bdacdefe4910792fa4d53a34acb0761e45aa8b4f95535fb1a668ba329c6d2ca`
- live `SKILL.md` sha256: `5edba30a12daebcd6cb26bdeeff59c1a59df282d6655cb5fbb6bc9eb11851af1`
- byte-equal: `False`

