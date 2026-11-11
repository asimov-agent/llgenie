# Landing a PR in llgenie: the `auto-merge` job, its deferrals, and the traps

Merging is CI's action in this repo. `.github/workflows/ci.yml` has an `auto-merge` job (the shape is
`trending-local-llms`' `auto-merge` in `qa-validate.yml`) that squash-merges a pull request when its run is
green **and** the PR is conflict-free. The agent never runs `gh pr merge` itself: it pushes, drives the PR
green and stops.

## The guards, and why each one exists

```yaml
needs: [guard, ci-images, linux, macos, engine-base, engine-matrix, engine-image, linux-published]
if: >-
  always() && !failure() && !cancelled() &&
  needs.<job>.result == 'success' && …            # EVERY need, not just !failure()
  github.event_name == 'pull_request' &&
  github.event.pull_request.draft == false &&
  (head.repo.full_name == github.repository ||
   head.repo.owner.login == '<owner>') &&
  github.head_ref != 'main'
```

- **`needs.<job>.result == 'success'` for every need** — a SKIPPED job satisfies `!failure()` but is not a
  passed job. Without it a PR whose `linux` or `macos` job was skipped merges as "green".
- **`always()` is still required** because a push-only job (`engine-published-test`) is skipped on a PR; it
  is deliberately *not* in `needs:`, and `always()` lets the merge job run when its own needs are done.
- **`--match-head-commit <sha>`** pins the merge to the commit the run validated: a push after the run
  started leaves the PR open for the newer run.
- **Owner PAT, never the job token** — a merge made with `GITHUB_TOKEN` starts no workflows, so the
  post-merge `main` run (which publishes the engine images) would never happen.
- **`make verify-closure PR=<n> REPO=<repo>`** after the merge: reads the merged PR's own
  `closingIssuesReferences` and fails naming the issue when a claimed `closes #n` is still open. A body
  that names an issue in prose without the keyword otherwise leaves it open on a green run.

## Deferrals: what the job prints and what you do instead

| GitHub says | meaning | what to do |
|---|---|---|
| `mergeStateStatus: CLEAN` | green + no conflicts | nothing — the job merges it |
| `DIRTY` | conflicts with the base | rebase the branch |
| `BEHIND` | stale branch | rebase the branch |
| `BLOCKED` | a required check or review is pending | see the review trap below |
| draft / third-party fork / head moved | not this run's decision | nothing |
| `do-not-merge` label | the human hold | a reviewer removes it; the next green run merges |

A deferral is exit 0 with a printed reason — never a failed run. `BLOCKED` and `REVIEW_REQUIRED` are the
states that cost the most time to diagnose; start from `gh pr view <n> --json
mergeable,mergeStateStatus,reviewDecision,reviews`.

## Trap: an existing PR never picks up a newly-merged CI job

A `pull_request` run is created only by a **push to the branch** (or a re-run of that same run). A job added
to `ci.yml` on `main` therefore does not run for a PR whose last run pre-dates it — and `gh run rerun`
re-executes the *same* workflow definition, so it will not contain the job either. Rebase the branch (or
push an empty commit) to create a fresh run. Expect the first minutes to look "not working": the job list
grows as `needs:` finish, so a missing `auto-merge` entry early on proves nothing.

## Trap: the review requirement the ruleset does not show

`mergeStateStatus: BLOCKED` with `reviewDecision: REVIEW_REQUIRED` and **zero reviews** is a review
requirement no bot can satisfy — a bot approving its own work is not a review. Before concluding the merge
job is broken, check the observable settings:

```bash
gh api repos/<owner>/<repo>/branches/main -q .protected                 # protected true/false
gh api repos/<owner>/<repo>/rulesets -q '.[] | "\(.id) \(.name) \(.enforcement)"'
gh api repos/<owner>/<repo>/rulesets/<id> -q '[.rules[].type] | join(", ")'
gh api repos/<owner>/<repo>/rules/branches/main                         # effective rules
```

A repo-level ruleset showing only `deletion, non_fast_forward` while every merged PR carries an approving
review means the requirement is somewhere the API view does not show (Settings → Rules, or the base repo's
fork-PR policy). Report that honestly and name the two ways out: a human approval for that PR, or scoping
the rule so the bot account can land its own PRs.

## Fork heads: accept the owner's fork, never delete its branch

Every agent PR here is pushed to the owner's fork and opened cross-repository (see the remotes section of
SKILL.md). So:

- a head condition written as `head.repo.full_name == github.repository` (copied from a sibling repo whose
  bots push in-repo) excludes **every** PR this repo opens — it fails silently, because a skipped job looks
  like "nothing to merge";
- accept `head.repo.owner.login == '<owner>'` in addition to the base repo, and let any other fork stay
  manual;
- merge a fork head **without** `--delete-branch`: the base token has no write access to the fork, and
  asking it to delete would fail a run whose merge already succeeded. Read `headRepository` from the same
  `gh pr view` and pass the flag only when it equals the base repo; print that the branch stays.

## Testing an auto-merge decision (no mocks of the product)

A fake `gh` on PATH that records argv and answers `pr view` / `issue view` / `pr merge` is the tested shape:

- **Embed fixture data as JSON text, not Python literals.** `json.dumps(fixture)` pasted into the generated
  script emits `false`/`null`, which the child Python cannot parse (`NameError: name 'false'`). Generate
  `PR = json.loads({json.dumps(fixture)!r})` (one level of `!r`, not two — double-encoding yields a JSON
  *string* and the product's `.get()` fails on `str`).
- **Let the fake change state** after a mutating call (write a marker file on `pr merge`, answer `MERGED`
  afterwards) instead of returning one static fixture — otherwise the post-merge closure check reads `OPEN`
  and the test fails for the wrong reason.
- Assert the **argv** the product built (`--squash`, `--delete-branch` presence/absence,
  `--match-head-commit <sha>`), not a digest of it.

## Adding a job to `ci.yml` reds the skip guard

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` is a whitelist over every job-level and
step-level `if:` in `ci.yml` / `pipeline.yml` / `published.yml`. A new job whose `if:` is not in it fails
`make test-unit`. Do not loosen the guard: extend `_job_if_allowed` with a **documented branch** for the job
whose scope genuinely is the event itself (a merge job is `pull_request`-only because a push to `main` has no
PR to merge, and make cannot see the event before a step runs), keeping `!failure()` / `!cancelled()` in the
accepted condition. OS- and matrix-specific work still belongs inside make.

## Operational notes

- `gh label create do-not-merge --color B60205 --description '…'` before shipping the job: the label does
  not exist on a fresh repo, and the hold is only real once it does.
- Verify the decision against the REAL PR without merging:
  `make auto-merge PR=<n> REPO=<owner>/<repo> HEAD_SHA=<sha> DRY=1` — it prints the fields it read and the
  reason it would defer.
- Run local `make test-unit` suites **one at a time**. Two concurrently trip the Hub's shared rate window
  and the live-link tests then red a hermetic gate with `HTTP Error 429`, which looks like your change.
