# Landing PRs: the auto-merge job, and the gates that surround it

llgenie lands a PR through CI. The agent still never runs `gh pr merge` by hand; an `auto-merge` job does,
once the run is green and the PR is conflict-free. This file is the depth behind that job plus the traps
that cost time when you add or change a CI gate here.

## The shape — the merge lives on `workflow_run`, not on `pull_request`

A fork-opened PR's `pull_request` run gets NO repository secrets, so a merge job inside that workflow reads
an empty token and defers every fork PR while its checks stay green. The merge therefore lives in its OWN
workflow, triggered from the BASE repo's completed run:

```yaml
name: auto-merge
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
…
      - run: make auto-merge PR=… REPO=… HEAD_SHA=… ACTOR=…   # GH_TOKEN / BUMP_TOKEN: the owner PAT
```

- `workflow_run` fires only once the workflow exists on the DEFAULT branch — the PR introducing it needs a
  human merge, so never tell the user the queue is self-merging before that lands.
- Check out the base branch, never the PR head (the job holds a write token); resolve the PR from
  `github.event.workflow_run.pull_requests[0]` and pin `HEAD_SHA` to that run's head SHA.
- A missing token is an explicit `exit 2` with an `::error::`, never a quiet deferral.
- Keep the whole decision inside `scripts/auto_merge.py` (state read, author gate, review bypass, merge,
  closure verify) so a fake-`gh` unit test covers it; the workflow only supplies numbers and the token.

`make auto-merge` → `scripts/auto_merge.py`: ONE
`gh pr view --json state,isDraft,mergeable,mergeStateStatus,reviewDecision,headRefOid,labels,headRepository,author`,
the author gate, then either a deferral (printed, exit 0) or
`gh pr merge --squash [--admin] --match-head-commit <sha>`, then `make verify-closure`
(`scripts/verify_closure.py`), which fails when a claimed `closes #n` is still open.

## Decision table

| what the `gh pr view` says | outcome |
|---|---|
| every needed job `success` + `mergeStateStatus: CLEAN` | merged, head pinned, branch deleted (same-repo head) |
| `DIRTY` / `BEHIND` / `UNKNOWN` | deferred: conflict / stale / not computed |
| `BLOCKED` + `reviewDecision: REVIEW_REQUIRED` + author passes the trusted gate | merged with `--admin` (the PAT is the author, so no approval is possible) |
| `BLOCKED` for any other reason, or the author is a stranger | deferred |
| draft, `main` head, third-party fork | never |
| head SHA moved since the run | deferred — the newer run decides |
| `do-not-merge` label | held; the label is the human escape hatch |

## Rules that cost time to learn

- **This repo's PRs are cross-repository.** Agents push to the owner's fork and open PRs from it, so
  `head.repo.full_name == github.repository` skips every PR the repo opens. Sibling repos whose bots push
  in-repo carry that condition; copying it here silently disables the gate. Match the base repo **or** the
  fork **owner** (`head.repo.owner.login`), never a wildcard or a negation.
- **`--delete-branch` only for a same-repo head.** The base token cannot delete a branch in the fork, and
  asking it to fails a run whose merge already succeeded. Read `headRepository` from the same `gh pr view`
  and omit the flag for a cross-repository head; print that the branch stays.
- **"Green" means every needed job SUCCEEDED.** `!failure()` is satisfied by a SKIPPED job (a collapsed
  matrix, a job cancelled by a concurrency group). Require `needs.<job>.result == 'success'` per PR-relevant
  job, and keep a push-only job out of `needs:` (it is skipped on a PR and would skip the dependent job).
- **A new job or step does nothing for PRs that are already open.** A `pull_request` run starts on a push,
  and a re-run replays the same merge ref — which predates the new job. An open PR needs a push/rebase to
  pick it up.
- **Merge with the owner PAT, never the job token.** A merge made with `GITHUB_TOKEN` starts no workflows, so
  the post-merge run on `main` (which publishes to GHCR) never happens.
- **Deferrals are exit 0, not failures.** `BLOCKED` (stale merge-commit checks after `main` moves) clears on
  a fresh run.
- **`reviewDecision: REVIEW_REQUIRED` is cleared with `--admin`, not with an approval.** The owner PAT is
  the author of every PR here, and GitHub refuses a self-approval, so an approve-then-merge path can never
  succeed — it is dead code that reports a policy block forever. The script instead takes one branch: when
  `mergeable: MERGEABLE` + `mergeStateStatus: BLOCKED` + `reviewDecision: REVIEW_REQUIRED` and the AUTHOR
  GATE already passed (owner / WRITE collaborator / bot-as-run-actor), merge with
  `gh pr merge --squash --admin --match-head-commit <sha>`. Order matters: the author check runs BEFORE the
  bypass, so a stranger's green PR still defers. The bypass must be one explicit branch that prints why, and
  a failed bypass (write-only token, no ruleset bypass) must go RED rather than defer at exit 0.
- **A trusted author's fork PR is merged, not skipped.** The condition is the base repo OR the owner's fork
  (`head.repo.owner.login`), and the AUTHOR gate is what decides — never gate the merge on the head repo
  alone, or every agent PR (pushed to the fork) is excluded while its checks stay green.

## The skip guard will red your new job

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` whitelists every job-level `if:` in
`ci.yml`/`pipeline.yml`/`published.yml` ("a job may wait for its needs, or skip the none placeholder row").
A new job carrying a condition reds `make test-unit`. The fix is ONE documented exception in
`_job_if_allowed` matching the exact semantics (event scope + `!failure()` + `!cancelled()` + the non-draft
guard) — never delete the assertion, never widen it to "any `if:` is fine".

## Testing a gate script with a fake `gh`

Same pattern as the bot suites: a `gh` script on PATH that appends `json.dumps(sys.argv[1:])` per call and
answers `pr view` / `issue view` / `pr merge` from fixtures — the product's own argv and env are what the
test asserts.

- **Embed the fixture as a JSON STRING and parse it in the fake:** `PR = json.loads({json.dumps(pr)!r})`.
  Writing `PR = {json.dumps(pr)}` emits Python `false`/`null` → `NameError` inside the fake, which surfaces
  as a product failure. Wrapping it twice (`json.dumps(json.dumps(pr))`) double-encodes, so the product's
  `json.loads` returns a *string* and every `.get(...)` dies with `AttributeError: 'str' object has no
  attribute 'get'`.
- Make the fake change state: writing a marker file on `pr merge` and flipping `pr view` to `MERGED` lets one
  test cover merge-then-verify instead of pinning a fixture that lies about the post-merge state.
- **Every API the product newly calls needs an arm in the fake, or the WHOLE existing suite fails.** Adding an
  author gate made the script call `gh api repos/<o>/<r>/collaborators/<login>/permission`; the fake answered
  with its error path, so every merge test failed at once rather than only the new one. Give the fake a
  `permissions={"<login>": "admin|write|read"}` fixture answering `.permission` (empty for an unknown login)
  the moment the product gains the call — and keep the fixtures explicit: a test that means "a stranger" passes
  `permissions={}` so it cannot be authorised by a default.

## Verifying a change here

- Decision only (no merge, no token): `make auto-merge PR=<n> REPO=asimov-agent/llgenie HEAD_SHA=<sha> DRY=1`
  prints the state map and either the deferral reason or "would squash-merge".
- Closure proof on any merged PR: `make verify-closure PR=<n> REPO=asimov-agent/llgenie`.
- `gh pr checks <n>` exits non-zero and prints "no checks reported" while a fresh head has no run yet; read
  `gh run list --branch <b> --json databaseId,status,headSha` instead of parsing its JSON.
- A push to a PR supersedes its own run (per-ref concurrency), so the newest head can sit `pending` while the
  previous run reports `cancelled`. That is the pipeline working, not a stall.

## Driving a bot run

- `make issue-bot-dispatch REPO=… DRY=1` prints the exact issue + branch the bot would pick — the same code
  path, so use it instead of guessing.
- Labelling an issue `agent:implement` itself dispatches a run; a run waiting on the `issue-bot` concurrency
  group implements whatever is free when it starts, so cancel a queued dispatch you do not want (and do not
  label an issue you are implementing by hand).
- A cancelled run's claim keeps its issue occupied until the claim TTL expires; a stopped agent leg has
  usually pushed nothing, so nothing is salvageable from it.
- To give a stalled run a clean budget: `gh run cancel <id>`, then
  `gh workflow run issue-bot.yml --ref main -f issue_number=<n>`, and check
  `gh run list --workflow issue-bot.yml` first so the pinned dispatch does not queue behind a live run and
  implement the same issue twice.
