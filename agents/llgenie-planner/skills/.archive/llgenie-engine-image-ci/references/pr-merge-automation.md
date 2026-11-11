# PR merge automation: the job that lands a green PR, and the traps in it

Read this when touching `.github/workflows/ci.yml`'s `auto-merge` job, `scripts/auto_merge.py`, or when a
green PR did not land and you are about to hunt a policy bug.

## The division of labour

- The agent pushes the branch, drives the PR green, and **stops**. It never runs `gh pr merge` (no `--squash`,
  `--merge`, `--rebase`, `--auto`, `--admin`) and never pushes to `main`.
- CI's `auto-merge` job lands a green, conflict-free, non-draft PR whose head is this repo or the owner's fork.
- A machine approval is not a human review: when the job posts `gh pr review --approve`, the body names the job,
  and any reader must be able to tell. Check `gh pr view <n> --json reviews` before treating `APPROVED` as
  sign-off.
- When the job defers, the reason goes **on the PR** (one comment per head SHA) and
  `make auto-merge-explain PR=<n> REPO=<owner/repo>` prints the same verdict writing nothing. A reason that
  lives only in a run log costs the next reader several round trips.

## The gates, and the defect behind each

| Gate | Why | Defect if omitted |
| --- | --- | --- |
| `needs.<job>.result == 'success'` for every PR-relevant job | a **skipped** job satisfies `always() && !failure()` | a merge lands a PR whose `linux`/`macos` job never ran |
| `--match-head-commit <sha>` | a push after the run started must not be merged by the stale run | an unvalidated commit lands |
| merge with the owner PAT, never `github.token` | a job-token merge starts no workflows | the post-merge `main` run (which publishes engine images) never happens |
| head is this repo **or** `head.repo.owner.login == 'andyholst'` | every agent PR is cross-repository (fork head) | a same-repo-only condition skips *every* agent PR |
| `--delete-branch` only for a same-repo head | the base token cannot delete a branch in the fork | the flag fails a run whose merge already succeeded |
| `mergeStateStatus == CLEAN` | `DIRTY` = conflicts, `BEHIND` = stale, `BLOCKED` = check/review pending | merging a conflicted or stale PR |
| defer (exit 0, printed reason) on every non-CLEAN state | a deferral is not a failed run | a red pipeline on a policy decision |
| `do-not-merge` label = human hold | a reviewer mid-read must win | CI merges under a reviewer |

## A review-blocked green PR

`mergeable: MERGEABLE` + `mergeStateStatus: BLOCKED` + `reviewDecision: REVIEW_REQUIRED` (0 reviews) is
procedural, not red — the run itself is green. The job may clear it by approving **with the other allowed
identity**:

1. `gh api user --jq .login` → the merge token's own account.
2. Compare with the PR author. **Equal ⇒ stop**: GitHub refuses a self-approval, so defer and say exactly that
   in the comment (this is the common case when the fork owner pushes and the token is theirs).
3. Author must be one of the repo's two allowed logins (`andyholst`, `asimov-agent`). A stranger's PR is never
   approved, however green.
4. `gh pr review <n> --approve --body '<names the job and the issue>'`, **re-read** `pr view`, and merge only if
   the state became `CLEAN`.

Never generalise this to other blockers: conflicts, staleness, drafts, third-party forks, a moved head and
`do-not-merge` all defer regardless.

## "Why is this green PR not merged?"

Check the run's unfinished jobs first — the `auto-merge` job is only **created** once its `needs:` complete, so
a PR whose slowest job (`macos / unit`, measured ~1 h) is still running has had **no merge attempt at all**.
`gh run view <run> --json jobs -q '[.jobs[] | select(.status != "completed") | .name]'` answers it in one call.
Then `make auto-merge-explain PR=<n> REPO=<owner/repo>` for the state verdict.

## Adding the job (or any job) to ci.yml

- `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` is a whitelist over every job/step `if:`.
  Extend `_job_if_allowed` with a narrowly-matched, documented exception; do not loosen the guard. An OS or
  matrix decision belongs in make (`make ci-*`, `make test-engine-stage`), not in a workflow `if:`.
- The job must be `always() && !failure() && !cancelled()` so a failed sibling still lets the merge decision run
  (it then defers on state) — and must not turn a deferral red.

## Testing it: fake `gh`, marker-file state

A fake `gh` on PATH that records argv is the no-mock way to lock this, and **the fake must flip its answers
through marker files** so ORDER is provable:

- `pr view` reads the fixture; `pr review` touches `<log>.approved`; `pr merge` touches `<log>.merged`; a later
  `pr view` answers with the flipped `reviewDecision`/state.
- Assert `calls.index(["pr", "review"]) < calls.index(["pr", "merge"])` — that is the approve-then-merge
  contract, and the re-read after an approval is what makes it real.
- Embed fixtures as `json.loads('<json>')`, never a rendered literal: `json.dumps(...)` inside the template
  emits Python `false`/`null` (`NameError: name 'false' is not defined`), and double-wrapping makes the
  product's `json.loads` return a **string** (`'str' object has no attribute 'get'`). Both look like product
  bugs and cost a debugging round.
- Also assert the negative branches: same-account author (no `pr review`), non-allowlisted author (no
  `pr review`), `DIRTY`/`BEHIND` (no `pr review`), and `explain` invoking no writing verb at all.

## Related policy gates

- `AGENTS.md` is **write-protected for the agent**: a policy change that needs a rule there is proposed as
  exact markdown in the PR body for the owner. A timed-out approval prompt is not consent, and routing the edit
  through another tool is refused.
- Every deferral/approval behaviour needs a spec scenario in the OpenSpec change with a `- **Test:**` line, and
  the test body carries `# Given / # When / # Then` markers — a scenario without a test, or a test without a
  scenario, is a review finding.
