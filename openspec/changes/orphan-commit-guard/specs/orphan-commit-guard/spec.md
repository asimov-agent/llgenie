## ADDED Requirements

### Requirement: An orphan commit on a merged PR's branch is detected and named

The repository SHALL provide `make check-orphan-commits`, which reads the merged-PR head map, the open-PR head map, and every remote branch tip, and fails non-zero naming each orphan commit when a same-repo remote branch is the source of a MERGED pull request, its current tip differs from that merged PR's head sha, the tip is not an ancestor of `origin/main`, and no open pull request covers the branch. Each orphan SHALL be reported as `orphan: <branch> <sha> (merged PR #<n>, merged <mergedAt>)` so the branch, the sha and the merged PR are all named. A residue recorded in the baseline file `data/orphan-baseline.json` as a `(branch, merged PR number)` pair SHALL still be NAMED — reported as a tolerated baseline residue — but SHALL NOT fail the run (its cleanup is tracked board work); an orphan whose pair is not recorded SHALL fail exactly like any other orphan.

#### Scenario: Post-merge push to a merged PR's branch is an orphan

- **WHEN** a branch carried a merged PR (head `A`), the branch exists again on the remote with tip `B` where `B != A`, `B` is not an ancestor of `origin/main`, and no open PR names that branch
- **THEN** `check-orphan-commits` exits non-zero and its output names the branch, sha `B`, and the merged PR number

#### Scenario: A branch whose tip is the merged head is not an orphan

- **WHEN** a merged PR's branch still exists on the remote with tip equal to that PR's recorded head sha
- **THEN** the run reports no orphan for it and exits zero

#### Scenario: An open PR covering the branch is not an orphan

- **WHEN** a branch carries commits not reachable from `main` but an OPEN pull request names that branch
- **THEN** the run reports no orphan for it (in-flight work is not orphaned work)

#### Scenario: A tip already merged into main is not an orphan

- **WHEN** a branch's tip is an ancestor of `origin/main` (the work landed)
- **THEN** the run reports no orphan for it regardless of merged-PR head equality

#### Scenario: A commit whose patch already landed by squash is not an orphan

- **WHEN** a branch commit is unreachable from `origin/main` by sha (the repo squash-merges, so its sha never appears) yet patch-equivalent to an upstream commit (`git cherry`)
- **THEN** that commit is not enumerated as an orphan

#### Scenario: A filed baseline residue is named yet tolerated

- **WHEN** an orphan's (branch, merged PR number) pair is recorded in `data/orphan-baseline.json`
- **THEN** the run names it as a `tolerated baseline residue` (same branch/sha/PR line, prefixed) and exits zero

#### Scenario: A baseline entry shelters nothing else

- **WHEN** an orphan's (branch, merged PR number) pair is NOT recorded — including the same branch re-cut by a different merged PR than the recorded entry
- **THEN** the run exits non-zero and names it as a failing orphan
