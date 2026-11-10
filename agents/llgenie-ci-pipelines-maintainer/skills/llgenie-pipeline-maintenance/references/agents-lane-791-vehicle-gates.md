# Landing an `agents/<profile>/` #791 pointer vehicle: the six CI guard gates and their exact shapes

A #791 vehicle (a text-only change under `agents/<lane>/` plus the change-note trio, e.g. a drill-point tree-rollout) reds `guard`/`scope` steps in CI unless each shape is exact. Measured 2026-11-06 on PR #1853 (#1849): it went through three failure rounds before green. The failing step's log line is the ONLY reliable signal — read the exact violation, never the run colour.

## The gates (run by guard/scope jobs from the LIVE PR body via `gh api pulls/<n> --jq .body`)

1. **`check-pr-closing`** (#1329/#1417): every claimed issue needs `closes #N` **adjacent** in BOTH the squash text (joined commit messages) AND the PR body, and the two close-sets must match. `closes **#N**` and `closes:#N` MISS. A claim is `Issue: #N` or a subject ending `(#N)`. Fix: put `closes #1849` in the commit subject/body AND the PR body. A commit with NO subject/body split (whole `Issue:/Fix:/...` on one line) becomes the subject and can't be matched — always split subject from body.
2. **`check-pr-agents-line`** (#792/#845): body needs the `AGENTS:`/`BASE:` lines `make bot-preflight` writes. bot-preflight differs against fork `origin/main` and can falsely list many profiles; verify the true changed-profile set with `git diff --name-only <truebase>`.
3. **`check-pr-sync-line`** (#1724): a diff under `agents/<p>/` needs `SYNC: <p> make sync-agent-profile PROFILE=<p>` per changed profile.
4. **`check-pr-openspec-change`** (#1807): the diff must add `openspec/changes/<n>/` OR the body must carry `OPENSPEC: <active-name>` naming a non-archive change-dir with a `tasks.md`. Precedent: security lane's #1819 used `OPENSPEC: agent-profile-tree` with no openspec files.
5. **`check-pr-acceptance`** (#1792): the PR closes an issue whose `## Acceptance criteria` has unchecked `- [ ]` items → name them out-of-scope under **`## Not covered`**, and each bullet MUST end with `#<n>` (regex `^-.*\s*#\d+\s*$`) and contain the criterion's first-3 normalised words. Do NOT tick the issue boxes — write-back is reviewer-gated (#1644); the lane never self-ticks (#948).
6. **`check-pr-base`** (#845): the branch must be cut from the LIVE base tip. An older `upstream/main` cut reds once the base advances. Fix: `git fetch <canonical> main && git rebase <new-base> && git push --force-with-lease`. CI's `origin/main` = the canonical repo's main.

## Practical notes

- After a body-only fix (no commit change): `gh run rerun <id>` re-fetches the LIVE body, which is read at job start — a rerun picks up the fixed body without a new commit.
- After a commit change (rebase/amend): force-push to the canonical upstream branch and confirm `gh api pulls/<n> --jq .head.sha` changed before believing a new run is evaluating it.
- A `check-pr-closing` LOCAL run against a stale base (old fork `origin/main`) sweeps in hundreds of historical issue claims → false violations. Reproduce the exact runner command (CI passes `--base origin/main` after fetching live) to avoid chasing ghosts.
- The `## Not covered` bullets must END with the number (`#1849`, no trailing `)`) and carry the leading words — a bullet ending `(#N)` is NOT matched.
- Rebase is safe only on a branch with ONE lane's fresh commit; fetch immediately before; `--force-with-lease` never bare `--force`.
- A cross-lane fleet-level AC (requiring ALL lanes) cannot be proven by a single vehicle — name it out-of-scope under `## Not covered` with the umbrella issue as the linked work item.
