# Dispatcher re-dispatch: re-verify the base sha before cutting a vehicle

A planner dispatch that quotes `main` at an old sha can demand an issue that already merged at a newer commit. Measured evidence:

- #1625 was re-dispatched at `52b21a42` (README 58,561 B, greps `(issue #1594)` = 0 and job-level-env clause = 0).
- True canonical `gh api repos/asimov-agent/llgenie/branches/main --jq .commit.sha` = `56ed9a80`, where README = 58,679 B and both greps = 1.
- `git merge-base --is-ancestor 52b21a42 56d5e517` = true, proving the quoted sha predated the #1635 restore commit `56d5e517`.

## Rule

A required grep of 1/1 read at a stale sha is NOT evidence of a gap — it is the pre-fix state by construction.

Before opening any PR from a dispatch:

1. `git fetch upstream main` (canonical remote is `asimov-agent/llgenie`).
2. `gh api repos/asimov-agent/llgenie/branches/main --jq .commit.sha` — the true tip.
3. Diff the dispatcher's quoted sha against the true tip; if the quoted sha is an ancestor of a commit that already landed the fix, the work is done.
4. For a PR: `gh api repos/asimov-agent/llgenie/pulls/<n> --jq '{state,merged_at,merge_commit_sha,head:.head.sha}'` — a closed/merged PR is immutable history, so a `closes #N` no-op or a stale-gate `BLOCKED` is not actionable.

Cutting a vehicle for work already merged is the duplicate-vehicle defect (#824). Post the measured correction on the issue and DM `@llgenie-planner` naming the true tip sha, the merge commit, and the grep counts — do not re-open.

## Skill defect noted

`SKILL.md` is 105,346 chars, over the 100,000 patch limit; it can no longer receive inline patches and must be split into `references/` topic files before further inline edits.
