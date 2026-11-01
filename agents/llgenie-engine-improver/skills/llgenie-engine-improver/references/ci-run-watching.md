# Watching an engine-build verification run (is it mine, is it alive, is it green?)

Engine-build runs are long (a cold CUDA/ROCm cell can build for 70+ min) and the workflow serialises
cells across runs, so most of the time spent "waiting for verification" is actually spent correctly
reading run state. Get the state read right before drawing any conclusion about the build or about your
own PR.

## Verify the PR head from the API, not from a fetch ref

`refs/pull/<n>/head` (and a cached `git rev-parse` of it) can keep serving a **pre-force-push commit** —
typically a parent of the current head — so a reader concludes the branch still carries edits the last
push already reverted. The authoritative head is the API: `gh api repos/<owner>/<repo>/pulls/<n> --jq
.head.sha`, cross-checked with `refs/heads/<branch>`. Quote that sha and its `updated_at`; never assert
head state from a local fetch ref or by reading a commit's tree instead of the branch tip. Immediately
after a push the API can still serve the pre-push head and `updated_at` for a few seconds — re-read once
before concluding the push failed; the push's own `old..new` line is the immediate fact.

## Poll the run you dispatched, not the PR's CI run

A `gh pr` push triggers a `pull_request` CI run and, separately, your `workflow_dispatch` engine-build
run. They are different run ids. Polling the PR's CI run and reading its `success` as "my engine build
passed" is the classic wrong answer — the PR run is only the guard/holds.

- List candidates with `gh api repos/<owner>/<repo>/actions/workflows/engine-build.yml/runs?per_page=40`
  and filter `event == "workflow_dispatch"` — the PR CI run is `event == "pull_request"` and can never be
  your confirm.
- Keep the dispatch run id the API returned at dispatch time and poll that id directly.
- A `pull_request` run appearing "success" while your dispatch is `pending` is not a contradiction; it is
  two different runs.

## Dispatch by branch name, never by SHA

The engine-build dispatch takes a ref; passing a bare commit SHA comes back **422**. Dispatch with
`ref=<branch-name>` (the head that branch name resolves to at dispatch time is what gets built, and it
is recorded as the run's `head_sha`). If you later amend the branch, the already-dispatched run still
points at the old sha — check whether the amendment touched anything the cells read before treating the
old-sha run as invalid evidence, rather than re-dispatching blindly.

**A dispatch re-resolves nothing.** `ref=<branch>` is resolved once, at dispatch creation: a
fast-forward push a minute later does not move an already-created dispatch, so a run whose `head_sha` is
an ancestor of your fix proves the defect, not the fix. Always read the run's `head_sha` back and compare
it to the PR head before calling it proof; if it is behind, cancel nothing — dispatch a fresh run and
quote the new id.

**A dispatch resolves the branch on the BASE repo, which is not the PR's head when the PR is
cross-repo.** For a PR whose head lives in a fork, `gh workflow run --ref <branch>` builds the base
repo's branch of that name — an older commit, or the right name on the wrong tree — and the run looks
green against code you never touched. Check `gh api repos/<owner>/<repo>/pulls/<n> --jq
'{head_repo: .head.repo.full_name, head: .head.sha}'`; when `head_repo` is a fork, fast-forward the base
repo's branch to the same sha before dispatching (the workflow only runs on the base repo), then verify
the run's `head_sha` equals the PR head.

## A `pending` run behind an `in_progress` run is not a defect

The workflow's concurrency means your dispatch sits `pending` while another run's cells hold the slots.
The run-level `updated_at` lags badly (it can stay frozen at creation time while jobs make real
progress) — it is NOT evidence of liveness either way. Read the *job* level:

```
gh api repos/<owner>/<repo>/actions/runs/<rid>/jobs
```

- A cell that is genuinely building has a `make build-engine …` step with `status: in_progress` and a
  `started_at` whose span to now keeps growing, and its later steps `pending`. That is a real cold build.
- cpu/vulkan cells finishing in ~12–15 min while rocm/cuda run 70+ min is normal (larger base images and
  toolchains), not a hang.
- Do **not** cancel a live run to free the queue. A job that never starts and one cancelled mid-flight
  look identical from an alarm; a `pending` confirm behind a real build is simply the queue doing its job.
  Report the measured cell states and keep waiting.

## Never write a measured acceptance number from a non-green run

Also: the acceptance run's `head_sha` must equal the PR's **live** head. A green run at an older sha
(or an off-branch tree) is not head-evidence even when the diff looks identical — re-dispatch at the
exact head before recording AC6. Compare trees with `git diff --name-only <run-sha> <pr-head>` and
check the *inputs the workflow actually reads* (Makefile, `.github/workflows/engine-build.yml`,
`tests/`, `scripts/engine_runner.py`, `containers/engines/entrypoint.sh`), not arbitrary repo files:
skill-reference docs under `references/` are NOT consumed by engine-build (grep the build tree to prove it).

For the PR's OWN diff (is my scope what I think it is?), diff against the **merge-base**, not `origin/main`:
`git diff --name-only $(git merge-base HEAD origin/main) HEAD`. Once main advances past the branch point,
`git diff origin/main HEAD` reports main's own newer commits as reverse changes and inflates the count —
seeing the planner's or another lane's files in "my" diff is main moving forward, not scope creep. Read
the merge-base diff before defending or deleting files.

A confirm run that has any red cell cannot supply the acceptance value (wall-clock, published image
size, throughput). Only a run whose build/detect/push/serve/install cells ALL concluded green at the
fixed head is the measurement. A run with two failed cells plus two in-progress cells proves only the
defect being fixed, never the fix. Say "in flight", never a fabricated or borrowed number.

## Reading a red install leg on a pre-fix run

When the confirm you dispatched lands on a head that lacks the fix, the install-leg cell reds on the
defect itself — that red is the reproduction, not a regression, and the same run's passing
build/detect/push/serve legs prove the rest of the seam is sound. Report it as "the defect reproduced at
this head, fix is in the next dispatch", not as a new failure.

## Triage a red cell by WHICH sub-step failed, before blaming your change

The install-leg (`make test-engine-install ENGINE=<id> ARCH=<arch>`) is a chain — `engine-launchers` →
`test-built-engine` → `ci-install-uninstall` (Makefile ~281–289) — and the same red run-level conclusion
hides three unrelated causes with three different owners. Never read "run failed" from the conclusion;
enumerate the run's jobs and read the **step-level** conclusion per cell, then read the failing step's
log tail. Group cells by step number (e.g. build-engine ≈ step 6, install-leg ≈ step 13) so a matrix of
one engine × arch shows at a glance which step each cell died on:

```
gh api repos/<owner>/<repo>/actions/runs/<rid>/jobs --jq '.jobs[]|.name'          # the cells
gh api repos/<owner>/<repo>/actions/jobs/<jid> --jq '.steps[]|"\(.number) \(.conclusion) \(.name)"'  # per-step
```

Read a job's log tail with `gh api repos/<owner>/<repo>/actions/jobs/<jid>/logs -H 'Accept:
application/vnd.github+json' --allow-escape-sequences` (redirect to a file, then strip ANSI and grep for
`FAIL|Error|exit status|not found`). The plain REST logs URL can answer 403 `AuthenticationFailed`;
the `gh api … --allow-escape-sequences` form is the one that works — do not hand-roll the auth.

Map the failing sub-step to its owner:

- **`engine-launchers` + `[install] FAIL cuda host without the NVIDIA CDI spec`** — the runner host has no
  `nvidia-container-toolkit`/CDI (`nvidia-ctk cdi list` empty), so it cannot docker-run the image with the
  host driver. This is **workflow/runner provisioning** (`.github/workflows/engine-build.yml` runs on
  plain `ubuntu-latest`, which ships no CDI), NOT a code or params defect and NOT your install-leg fix.
  It is the pipeline maintainer's gate; hand it there, do not weaken the (correct) CDI check to go green.
- **`ci-install-uninstall` + `touch …/bin/…: No such file`** — the CI fixture HOME has no `~/bin`; that is
  the seam's own `mkdir -p ~/bin` fix, verified when this leg reaches the final step and passes.
- **an earlier `make build-engine`/`engine_runner.py install` step** — a build/params failure, a different
  lane from the install-launcher seam; not evidence about an install-leg change.

## A red PR-CI job: enumerate by branch, then read the failing step

`pulls/<n>/checks` can 404 and an `actions/runs?head_sha=<sha>` filter can come back empty (the commit
filter is unreliable on freshly pushed heads). Enumerate the PR's own CI runs by **branch**:

```
gh api 'repos/<owner>/<repo>/actions/runs?branch=<branch>&per_page=10' \
  --jq '.workflow_runs[]|select(.event=="pull_request")|"\(.id) \(.name) \(.status) \(.conclusion)"'
gh api repos/<owner>/<repo>/actions/runs/<rid>/jobs --jq '.jobs[]|"\(.name) \(.conclusion)"'
```

The `pull_request` run's useful jobs are `guard`, the scope job (`make check-docs` / `ci-scope`), and the
`linux / …` unit jobs (`make ci-unit`, lint, openspec, install, cpu-health). The job name plus the
failing **step** name names the make target that reds — read the step, never only the run conclusion.

## A red `make check-docs` is usually the shared census gate, not your docs

`make check-docs` chains several scripts and prints its own `[check-docs] ok: every …` summary line
**before** it runs `scripts/check_architecture_census.py`. A job can therefore log that ok line and still
exit 1 — read the log lines *after* the summary: `[census-gate] measured-at: the doc's pointer <sha> is
not a real commit` / `no usable referent` is the census pointer gate, red on every PR while main's census
pointer is stale. It is the docs lane's root, not your engine change — do NOT edit your changelog docs to
appease it, and do not arm the PR as if it were green. Attribute the red to that gate in the report.

## A red `make ci-openspec` is an unticked task in the change you shipped

A scope job that reds on `make ci-openspec` is not a docs or format problem: the gate walks
`openspec/changes/<change>/tasks.md` and fails on any `- [ ]` left unchecked. One task commonly says the
cell must be **proven on a CI run from this PR** — that task is the gate that turns a params edit into an
actual build measurement, and it is also the first thing in the whole pipeline to see a real build defect
(a missing build backend, a CMake policy the base image's toolchain cannot parse).

- Dispatch the narrow cell (`-f engine=<id> -f arch=<v>`) at the PR head and poll THAT run — the task is
ticked by evidence, never by optimism or by deleting the line.
- Never check the box to go green: an unticked task that reds is a defect report, and the fix belongs in
the params/skill install row that the build reads.
- Each red at that cell is a NEW defect once the previous one is fixed (the build advances one stage per
  fix). Re-dispatch and re-read the failing sub-step instead of assuming the earlier fix was wrong.

## Arming auto-merge is a readback, not an exit code

`gh pr merge <n> --squash --auto` exits 0 and arms **nothing** when the PR is `mergeable_state=blocked`
(a red required check) — the same silent no-op as a non-default base. A moment after arming, re-read
`gh api repos/<owner>/<repo>/pulls/<n> --jq '.autoMergeRequest'`: `null` means NOT armed. Report
`auto=none (blocked: <the red check>)`, never "armed". A PR with a red check is not done-green and so not
"done" — fix the red or attribute it to another lane's gate first; arming is the trigger, and it only
holds on a PR whose only remaining blocker is the required review.

Three readback states, three different reports — do not collapse them:

- `autoMergeRequest: null` + `mergeable_state: blocked` — not armed (red required check).
- `autoMergeRequest` populated, `enabled_at: null`, state `blocked` — **armed but pending**: the arm held
  and is waiting on the required review/CI. Report `auto=armed (pending: <blocker>)`; this is the normal
  state while a re-run is in flight, not a failure to arm.
- `autoMergeRequest: null` with `mergeable_state: dirty` — **the base advanced into a conflict and GitHub
disarmed it.** A rebase, a re-push and a fresh `--auto` are required; the previous arm does not survive
  new commits on `main`, so after ANY rebase re-arm and re-read rather than assuming the old arm is still
  armed. The same base advance also invalidates the CI runs already at the old head: their verdicts were
  measured against a base that no longer exists, so they can be green and irrelevant — re-run at the new
  head before quoting them.

## Same cell, same head, different verdict → host-flaky, not a regression

Before treating a cell's red as caused by your commit, compare the SAME cell at a prior run on the same
code path (the same or an equivalent head): if that cell passed `engine-launchers` in run A (reached
`ci-install-uninstall`) and fails the CDI check in run B at the same head, the difference is the runner
host's CDI state, not the code. A fix is "verified" only on the cells a host can actually execute the leg
for: green non-CUDA install-legs (cpu/vulkan/rocm) prove the `~/bin` fix, while a cuda install-leg red on
missing CDI proves the host gap — report both facts separately and attribute each to its owner.
