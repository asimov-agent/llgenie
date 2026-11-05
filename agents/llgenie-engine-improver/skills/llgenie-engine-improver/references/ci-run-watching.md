# Watching an engine-build verification run (is it mine, is it alive, is it green?)

Engine-build runs are long (a cold CUDA/ROCm cell can build for 70+ min) and the workflow serialises
cells across runs, so most of the time spent "waiting for verification" is actually spent correctly
reading run state. Get the state read right before drawing any conclusion about the build or about your
own PR.

## Arm a watcher for a long run — never poll inside a code cell

A CI build cell can run 30–70 min. Two mechanics bite:

- **`execute_code` cells have a hard ~300 s cap and lose the kernel's state when they time out.** A
  `for _ in range(20): …; sleep(60)` polling loop dies at 300 s and takes your variables with it. Never
  put a multi-minute wait loop in an `execute_code` cell — do one short state read per call instead.
- **Wait with a background `terminal` job carrying `notify: true`** (`while :; do gh api …/runs/<id> -q
  '.status+" "+(.conclusion//"none")'; sleep 60; done`, appending to a scratch log), then poll that log
  with a short read. Or `gh run watch <id> --repo OWNER/REPO --exit-status` in the background.
- **Size the watcher to the run's own `timeout-minutes`, not a fixed loop count.** Compute the bound as
  (job `started_at` + `timeout-minutes` − now) + slack, and iterate enough to pass the run's
  self-termination instant. A watcher that expires before that instant reports `WATCHER_EXPIRED` and reads
  as "still running" when the truth is "I stopped watching too early" — a ~45-min watcher on a run whose
  cell self-cancels at ~240 min is guaranteed to expire first and produce a false in-flight verdict.
- **One live watcher per run.** When you extend or replace a watcher, kill the previous loop first
  (`kill <pid>` on the background shell you started), or two loops fire on the same run and you get
  duplicate/contradictory notifications plus a stale one resurfacing after you acted.

While that run is in progress at the branch head, do NOT push a new commit to that branch — a new
commit moves the head, makes the in-progress run stale, and `cancel-in-progress` turns an authorised
push into destruction of a live matrix. Commit locally (no push), arm the settle watcher, and push +
re-dispatch only after it concludes.

## Verify the PR head from the API, not from a fetch ref

`refs/pull/<n>/head` (and a cached `git rev-parse` of it) can keep serving a **pre-force-push commit** —
typically a parent of the current head — so a reader concludes the branch still carries edits the last
push already reverted. The authoritative head is the API: `gh api repos/<owner>/<repo>/pulls/<n> --jq
.head.sha`, cross-checked with `refs/heads/<branch>`. Quote that sha and its `updated_at`; never assert
head state from a local fetch ref or by reading a commit's tree instead of the branch tip. The branch
NAME is `.head.ref` (`.head.label` renders `owner:branch`); the PR JSON has **no** top-level `head_ref`
field, so a `--jq '{head_ref}'` projection returns `null` and reads as "branch unknown" when the branch is
fine — project `.head.ref`, or just read `.head.sha`, and don't report an in-repo PR as fork/missing on
that null. Immediately
after a push the API can still serve the pre-push head and `updated_at` for a few seconds — re-read once
before concluding the push failed; the push's own `old..new` line is the immediate fact.

**A bare `--force-with-lease` can refuse with "stale info" even though the remote is exactly what you
expect** — the local remote-tracking ref is stale. Fetch immediately before the force and use an
explicit lease against the sha you just read back from the remote:
`git push --force-with-lease=refs/heads/<branch>:<remote-sha> <remote> <new-sha>:refs/heads/<branch>`.
For a cross-repo PR (head lives in a fork), that remote is the FORK; pushing the same branch name to the
base repo leaves the PR reading its old head (or creates an unrelated stale branch there).
After every push, assert `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` equals the new commit.

**A report that "the head moved" is a claim to verify, not a reason to re-trigger.** A PR's `updated_at`
bumps on any comment or label edit, so it is not evidence of a new commit: compare `.head.sha` against
`repos/<fork>/git/ref/heads/<branch>` and the last PR commit date. When they all match, nothing moved —
a fresh CI run at the same head re-reds the identical gate, so report "no head move, nothing to
re-trigger" with the sha read back, instead of dispatching a redundant run.

## Poll the run you dispatched, not the PR's CI run

A `gh pr` push triggers a `pull_request` CI run and, separately, your `workflow_dispatch` engine-build
run. They are different run ids. Polling the PR's CI run and reading its `success` as "my engine build
passed" is the classic wrong answer — the PR run is only the guard/holds.

- List candidates with `gh api repos/<owner>/<repo>/actions/workflows/engine-build.yml/runs?per_page=40`
  and filter `event == "workflow_dispatch"` — the PR CI run is `event == "pull_request"` and can never be
  your confirm.
- Keep the dispatch run id the API returned at dispatch time and poll that id directly.
- **A run id created on the FORK 404s on the base repo, and vice versa** — a fork-dispatched proof read
  against `repos/<base>/actions/runs/<rid>` returns `Not Found`, which is NOT evidence the run was deleted
  or never existed. Read it from the repo you dispatched on (`repos/<fork>/actions/runs/<rid>`); the
  run's own `head_sha` still confirms it is the proof for the PR head.
- A `pull_request` run appearing "success" while your dispatch is `pending` is not a contradiction; it is
  two different runs.
- **An already-armed watcher outlives the head it was dispatched for.** A background `gh run watch <id>`
  (or a poll loop) fires on the run id it was given, long after the PR has advanced — a fork branch can
  move commits ahead (another lane fast-forwarding it) while the watched run still points at the older
  sha. When such a watcher reports `failure`, do NOT treat it as a gate red: re-read the PR's live head
  (`gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha`) and compare the completed run's `head_sha`
  against it. A run whose `head_sha` is behind the PR head is a historical verdict about a superseded
  commit, not evidence about the current one — re-arm on the run that actually sits at the live head (and
  dispatch a fresh one if none exists). Same head check as dispatch time, applied at completion time.

## A peer's "stalled / NO job in_progress" verdict is measured on ONE repo — read the repo the proof lives on

A stall claim ("head unchanged, same gates red, NO job in_progress") is about a *particular* repo's
runs. A box proof dispatched on the FORK (where a cross-repo PR's head lives) is invisible to a reader
enumerating the canonical repo's runs: the canonical PR suite's jobs are all `completed`, so the
measure reads "no job in_progress" while the fork's engine-build job is genuinely building. Before
accepting or relaying a stall verdict, enumerate BOTH: the canonical suite at the head AND
`repos/<fork>/actions/runs/<rid>/jobs` for the dispatch you created. Quote the repo in the finding.

**Judge a long cell against the SAME class's completed durations, not a generic floor.** "~2.5 h and still
in_progress" is mid-envelope when prior completed cells of that same engine×arch ran far longer: read
the historical cell durations (`actions/runs/<rid>/jobs` start/complete on older runs of the same
workflow) and compare elapsed to that class's own median/max, e.g. a source ROCm/cuda cell routinely
runs ~4 h before its own `timeout-minutes` cancels it. A cell inside its class envelope is NOT a stall,
whatever a wall-clock-only observer thinks; only elapsed past the class max (or past a 2×-slice-median
floor with no step completing) is a suspension candidate. Combined with the frozen-run-`updated_at` and
BlobNotFound-is-normal rules below, that is the full discriminator.

## `conclusion: failure` with ZERO materialized jobs is a workflow-level artifact, not your PR

A run can settle `completed / failure` while `actions/runs/<rid>/jobs` returns `total_count: 0` and the PR
shows none of its usual `linux / …` check-runs. That is NOT your matrix failing — the workflow was rejected
or cancelled before any job materialized (a just-rewritten workflow file, a `permissions`/token-scope
change, a YAML error in `on:`/`jobs:`). A real code red always leaves at least one job with a failing step,
so a zero-job `failure` is a config-level fault by construction.

Classify it before blaming the branch: if every recent PR head **and main's own recent merge heads** show
the same `failure`-with-no-jobs signature on the same workflow in `actions/runs?per_page=40`, it is a
repo-wide regression in the workflow lane — the workflow file changed on `main` and every head now inherits
it — not something your commit introduced. Name the commit that rewrote it
(`git log -1 --format=%h -- .github/workflows/<wf>`) and route the finding to the CI/pipelines owner. Do
NOT edit `.github/workflows/*` from an engine PR to work around it. Evidence to quote: the run's
`jobs` payload is `total_count: 0`, and a `--log-failed`/`--log` read of that run returns `log not found`
(the job never ran). Contrast with the OTHER reds at the same head that DO materialize a job (e.g. a
`scope` job failing on `make ci-openspec`) — those are real, separately-attributed gate verdicts.

## Dispatch by branch name, never by SHA

The engine-build dispatch takes a ref; passing a bare commit SHA comes back **422**, and `ref=refs/pull/<n>/head` comes back **422 too** — the `ref` field accepts only a branch or tag NAME, never a commit or a PR pseudo-ref. Dispatch with `ref=<branch-name>` (the head that branch name resolves to at dispatch time is what gets built, and it is recorded as the run's `head_sha`).

**A dispatch's REST response is `204 No Content` — an empty body IS success.** POSTing to
`.../actions/workflows/<wf>/dispatches` returns 204 with no body; a helper that does `json.loads(resp)` on
it throws `JSONDecodeError` and reads as a failed dispatch when it actually landed. Treat a 204/empty body
as accepted and confirm by listing the workflow's runs for the new id, not by parsing the dispatch reply.

**`engine-build.yml` is `workflow_dispatch`-ONLY — it has no `pull_request` trigger.** A PR push runs the
`pull_request` `ci`/`ci-scope`/holds workflows, but never an engine-build cell. So a cell is NEVER proven
by "the PR-triggered build" — the proof is always a fresh dispatch you dispatch yourself at the head. Do
not sit waiting for a PR-triggered engine-build that does not exist; dispatch it. If you later amend the branch, the already-dispatched run still
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

The silent failure signature: **the base repo carries a same-NAMED branch at an older commit, and the
dispatch builds THAT parent while you believe you proved the head.** Detect it by comparing the two
refs before dispatching — `git ls-remote <base> refs/heads/<branch>` vs `git ls-remote <fork>
refs/heads/<branch>` (they differ by the head's delta), or just read the dispatched run's `head_sha` and
compare to the PR head. Fix with a lease push carrying the base's current sha as the lease and the fork
head as the new value:

```bash
git push --force-with-lease=refs/heads/<branch>:<base-old-sha> \
  <base-url> <pr-head-sha>:refs/heads/<branch>
```

Then re-dispatch by that branch name and confirm the new run's `head_sha` == the PR head. Never cite a
run whose `head_sha` is a parent of the head as the cell proof, even when the diff looks identical.

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

## A cell killed by its own `timeout-minutes` settles `cancelled`, not `failure`

A job that exceeds the workflow's `timeout-minutes` comes back `status: completed`,
`conclusion: cancelled` — at both run and job level — and REST's run field `timed_out` is `null`.
That is indistinguishable from a manual cancel to a watcher printing `ci=completed concl=cancelled`,
so prove which one it was before writing any verdict:

- the cell's `started_at` + the workflow's `timeout-minutes` ≈ the run's settle time, the same
  `make build-engine …` step is still `in_progress` in the final step list, and `guard`/`matrix`
  concluded `success` ⇒ it hit its OWN cap;
- a manual/concurrency cancel leaves sibling steps aborted mid-way and usually a `cancel-in-progress`
  replacement run in the list.

Verdict text: **the build class does not finish inside the cell's time budget** — a CAPACITY finding,
not a code regression, and never a green. Never tick an acceptance box on a cancelled run (a cancelled
run supplies no measured number). Report the run id, the cap, elapsed wall-clock and the still-active
step, then ask for a budget decision — raise `timeout-minutes` and re-dispatch, or mark that proof
capacity-blocked — instead of blind-re-dispatching a third multi-hour run of the same class.

## A cancelled WAIT-GATE (`engine-pins`) means UNPROVEN — read which tag is 404, and check the producer ever started

`engine-pins` ("Wait until every repinned engine image is published") is not a build and not a test: it is a
poller that loops up to ~290 min printing `[pins] PUBLISHED <tag>` / `[pins] NOT PUBLISHED <tag> (HTTP
Error 404)` for every tag the pin-bump's params imply, then ends in whatever the babysitting run gives it.
A red `engine-pins` is therefore read from its LOG, not its conclusion:

- **A `cancelled` `engine-pins` is UNPROVEN, not a code red.** It proves only that some awaited tag was still
  404 when the run was killed — typically the slow cuda/rocm cells — while the cpu tag already reads
  PUBLISHED. Never report "the head is red / the rocm build fails" from a cancelled `engine-pins`; the
  honest verdict is "tag `<leaf>:<pin>-<hash>-<variant>` is not published yet, so this head is unproven".
- **Read the whole job log, not the tail.** `gh run view <rid> --job <jid> --log | grep '\[pins\]'` gives the
  per-tag PUBLISHED/404 roster; the tail is checkout-cleanup noise (`##[error]The operation was canceled` then
  orphan-process kills) that says nothing about WHY.
- **A 404 is "not built/published yet", never "build broken".** Confirm with
  `scripts/ghcr_publish_probe.sh` before drawing any build conclusion.

**Before blaming the engine ("rocm never completes"), check the PRODUCER ran at this head.** The pin-bump
PR's `engine-build-pr-trigger` starts the producer and waits on it; if that trigger itself is `cancelled`,
the producer never ran, so the cells were never exercised — the "build never finishes" symptom is really
"the build was never attempted". Enumerate `engine-build.yml` runs and confirm one exists at this head's sha
(`head_sha` match) before attributing anything to the build. A missing producer + a cancelled wait-gate is a
GATE-CHURN/idle problem (cancel-in-progress, frozen-reaper, or a babysitting cancel chain), not a compile
defect — the fix is to re-run the trigger, not to edit params/Dockerfile.

## `failure` + a frozen `in_progress` step + a 404 job log = a cell killed at the PROCESS level

Distinguish this from the `cancelled` timeout case above by the **conclusion**: there the frozen
`in_progress` step pairs with `conclusion: cancelled`; here it pairs with `conclusion: failure`. A cell can
settle `failure` while its `make build-engine …` step still renders `in_progress` and the step list freezes
there — that is neither a code error nor a timeout: it is the cell's own process killed mid-step (runner OOM,
disk, or other resource eviction), so GitHub never sealed the step status or the log. Corroborate before
deciding:

- **A completed job whose job log 404s is the tell, not a transient.** `gh api .../actions/jobs/<jid>/logs`
  answers 404 for a process-killed cell (its log was never finalized), whereas a normally-completed cell's
  log fetches fine even while the run is still `in_progress` (a sibling cell building). Retrying the 404 will
  not change it; do not read it as a rate-limit hiccup.
- **Read live state from the job endpoint** (`actions/jobs/<jid>`), not the run's cached `--json jobs` step
  render, which can keep serving a stale `in_progress` for a step that is really over.
- **Cross-check a suspected resource kill against a local build of the same commit.** If a local
  `make build-engine` of the identical tree compiles PAST the point where CI died (and keeps advancing — the
  compiler-PID churn test above), the CI red is a runner capacity kill, not a defect in your diff. Report it
  as a capacity finding (run id, elapsed wall-clock, the frozen step, the 404 log) and let a fresh cell retry;
  never attribute it to the code change.

## A board-wide check (`holds`) is stale after the board moves — rerun the ORIGINAL run, don't dispatch

The `holds` workflow audits the LIVE board, so a verdict it produced at your head becomes stale the
moment another PR's label or comment state changes. Two mechanics decide whether the PR's check-run
actually moves:

- **A fresh `gh workflow run` dispatch creates a NEW run that attaches NO check-run to the PR head** —
the PR keeps showing the old red. To move the check-run the PR displays, rerun the **original**
PR-triggered run: `gh run rerun <rid> --failed --repo <owner>/<repo>`, which re-executes its failed
jobs and updates that head's check-run in place.
- Recover a check-run's backing run id from its `details_url` — the check-run's own id is a JOB id, not
a run id: `re.search(r'actions/runs/(\d+)', check_run['details_url'])`.

## The job-log TAIL is post-job cleanup — grep the WHOLE log

`curl` the job log (`https://api.github.com/repos/<o>/<r>/actions/jobs/<jid>/logs`, header
`Accept: application/vnd.github+json`) to a file, strip the ISO timestamp prefixes, then grep the file
end-to-end for `FAIL|Error|exit code|make: \*\*\*|AssertionError|TIMEOUT`. Reading only the last
~1.5 KB of a failed job returns `Cleaning up orphan processes` / `Node.js 20 is deprecated` noise and
hides the real failing step; the actionable line sits somewhere earlier in a log that can be 100 KB+.

**`gh run view <rid> --log-failed` on a multi-job workflow concatenates EVERY failed job's log into one
stream, each line prefixed by the job name.** Reading the un-filtered tail before an `Error 2` therefore
shows a *different* job's failing step and sends you chasing the wrong gate. Always filter to the job
first: `grep '^linux / unit ' log` (or whatever the job name is), then read that job's tail before the
`Error 2`. The tell that you read the wrong job is an `Error 2` whose preceding lines name a `make` target
that job does not run.

## After publishing the missing artifact, RE-RUN the red gating run — do not wait for a push

`gh run rerun <rid> --failed --repo <owner>/<repo>` re-executes only the failed jobs of an existing run
(a branch-sourced `push` run included) and flips the run back to `in_progress` within seconds — read
that flip back as the confirmation the rerun actually landed (`gh run rerun` reporting success is not
proof by itself). This is the correct close for a publish-order red: prove the artifact is now in the
registry (`scripts/ghcr_publish_probe.sh` → PUBLISHED/200), then re-run the red `linux / unit` job so
the "every installed image is published" test executes against the now-present tag. Waiting for the
next unrelated main push leaves main red for no reason.

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

## Zero runs at a fresh head: full-sha, then base-staleness, then scheduling lag

After a push, `actions/runs?head_sha=<new>` can read **zero** while other PRs' runs flow. Read the cause
in this order before concluding anything about triggers:

- **Pass the full 40-character sha.** `head_sha=<short-sha>` silently matches nothing and returns zero —
  a short-sha query reads as a dead trigger when the trigger fired fine. Expand it first (`.head.sha` from
  the API, or `git rev-parse`), then re-query; only then believe a zero.
- **A PR whose base has fallen behind main reads `mergeable_state=dirty` / `mergeable=false`, and GitHub
  creates NO `pull_request` runs (and no check-suites) for it** — indefinitely. That is not lag and waiting
  never clears it. The fix is to **rebase onto the CURRENT `origin/main` and force-push**: the rebase
  rewrite re-triggers CI at the new head within seconds (measured: three runs appeared ~15s after the
  rebase push). Compare `base.sha` against a fresh `git fetch upstream main` first; if main has advanced,
  rebase — do not re-push onto the same stale base, and do not sit waiting for a run that will never spawn.
- **Only when the base is current** is a zero plain scheduling lag: do not re-push (under
  `cancel-in-progress` a re-push destroys a live run), prove the gate locally, and arm a watcher.
  Concretely:

- Read which gates the change will get from the workflow `on:` blocks. `scope.yml` (the `ci-scope` check)
  fires on `pull_request` with **no path filter** and always runs — it is the docs gate even for a
  docs-only diff. `ci.yml` skips a docs-only diff **at the trigger** (a path filter, issue #824), so a
  docs-only PR correctly gets `scope` + `holds` and no full CI matrix. An expected-absent run is a
  config+diff fact, not a fault.
- Prove the change where it is reproducible instead of waiting on the scheduler: run the exact failing
  gate locally at the pushed tree (`make ci-lint` for a linefeed/editorconfig red) and quote the local
  result as the fix evidence.
- Then arm a watcher that polls the runs-at-head once a minute for ~40 min and reports when runs appear;
  report "runs not yet scheduled at <sha>, fix proven locally" — never "CI did not run, so it is broken".

## Rebasing for a stale base: regenerate the generated index, never hand-merge it

A rebase onto current main almost always conflicts in `CHANGES.md`, because it is generated from
`docs/changes.d/` fragments and every merged PR adds a fragment row. Do **not** hand-resolve the conflict
rows — a hand-merge drops either your row or the rows main added while you were behind. Resolve it
deterministically: take main's side (`git checkout --ours CHANGES.md` during the rebase), stage it, then
regenerate from the current tree with `make changes-index` (runs `scripts/changes_index.py write` over all
fragments). Verify BOTH your fragment's row AND the rows main added survive (`grep` for each fragment
slug), then `git rebase --continue`. The regen is the merge. Run `make ci-lint` and `make ci-openspec` at
the rebased head before the force-push — `ci-lint` confirms a linefeed/editorconfig fix survived the
rebase, `ci-openspec` confirms no stray untracked `changes/*` dir is polluting the scan (an empty,
untracked `<change>-rootbroken/` diagnostic dir counts and must be removed, it is not part of the PR).

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

**`gh run view <rid> --log-failed` can come back EMPTY even when a job failed** — it filters for failed
*steps* and misses a job whose failure surfaces at the job/step-wrapper level. When it returns nothing, do
not conclude the job passed: read per-job instead — `gh run view <rid> --job <jid> --log 2>&1 | grep -iE
'Error|FAIL|exit code|make: \*\*\*'` (get `<jid>` from `actions/jobs` details or the check-run
`details_url`) — and enumerate steps first via `actions/jobs/<jid> --jq '.steps[]|"\(.conclusion) \(.name)"'`
to see which step is `failure`.

## A red `linux / unit` leg: attribute the failing TEST FILES, not the job name

The `linux / unit` job runs one giant pytest invocation (150+ files). A red on it names no single owner:
pull the failing files out and check whether any of them touch YOUR diff before blaming your change.

```
gh run view <rid> --repo <owner>/<repo> --log-failed 2>&1 | grep -iE 'FAILED|AssertionError|pytest|::' | head -40
```

`gh run view <rid> --log-failed` is the reliable reader here. `gh api … --jq` with a `select(...)`
expression mangles when it passes through a nested `bash -c` quoting layer (you get `unexpected token`, or
`accepts at most 1 arg(s), received 3`) — either build the jq as a single-quoted literal passed once, or use
`--log-failed` and grep, rather than stacking quotes through a shell wrapper.

The failing named files (e.g. an agent-profiles fold test, the dispatch-forms census, a skill-gap render
test) are almost always OTHER lanes' drift riding in the same suite. Name them, then verify.

Quote the run's own magnitude line from the `--log-failed` tail (`N failed, M passed, K deselected`) and
state explicitly that ZERO of the N carry your diff's target file — "4 failed, 2772 passed, 0 skill-gap
failures" is the verdict; "the unit leg is red" alone reads as your regression. Absence of your file
from the FAILED set is the proof your change's suites were green in that very run.

**When your change is ALREADY MERGED, main is red at the tip by definition — the 'green-on-main' proof is
unavailable, so compare against the MERGE PARENT instead.** Reproduce the exact failing test files in two
clean detached worktrees: the merged tip, and the tip's first parent (pre-merge main). Red at BOTH ⇒
pre-existing cross-lane drift, not introduced by your merge; red only at the tip ⇒ your merge caused it.

```
parent=$(git rev-parse <merge-sha>^)
git worktree add --detach /tmp/u-tip    <merge-sha>
git worktree add --detach /tmp/u-parent $parent
# run the SAME named test files in each; then
cd <repo> && git worktree remove --force /tmp/u-tip && git worktree remove --force /tmp/u-parent && git worktree prune
```

Report the real verdict as measured: the leg is red, the failing files are N of M that touch none of your
diff, and they red at the merge parent too — so the red is the other lane's drift, and your change's own
suites were green at the committed head. Never write "pre-existing" as a hunch or leave the head verdict
as 'owner merged through pending' once the run has actually concluded FAILURE.

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

## A stale `check-pr-closing` sweep is fixed by RETARGETING the PR base, not by pushing

`github.event.pull_request.base.sha` is frozen at the PR's recorded base and a plain head-branch push
does NOT advance it. Measured (PR #1453): base stuck at `23f9023` for 30+ min while `main` moved to
`309cdf69`; an empty-commit push carried the same stale base. The runner checks out `refs/pull/<n>/merge`
(head merged into CURRENT main) but feeds the guard the stale `PR_BASE`; so `git rev-list --no-merges
23f9023..merge` sweeps every main commit merged since — check-pr-closing claims #1467/#1470/#1471/#1506/
#1507/#1511/#1513, closes #1465/#1468/#1469/#1472/#1508/#1509, none authored by the branch.

Tell apart event-staleness from a real content defect: the failing run's log prints `PR_BASE: <old-sha>`
(the tell) and the "claimed" issues are main's own commit subjects that are not even in HEAD. Prove green
locally with `check_pr_closing.py check --body-file <body> --base refs/remotes/origin/main --rev HEAD`
(rc 0) before touching anything.

The reliable lever is a **REBASE-free retarget**: `gh pr edit <n> --base main` forces GitHub to recompute
`base.sha` to current main (metadata-only, changes no tree); then one ordinary (fast-forward, no force)
push carries the corrected base in the next synchronize event. Re-read `gh api repos/<o>/<r>/pulls/<n>
--jq .base.sha` against `commits/main` before and after — the retarget is what actually moves it. A BASE
CHANGE alone may not dispatch CI; the push after it does. Squash-close range then excludes main's commits.

Second, a branch that swaps from guard-red to scope-red can be a genuine second defect: `make ci-lint`
reds on any file missing a trailing newline. Check the failing step, not just the job: `gh run view <rid>
--log | grep -A3 'LINT FAIL'` names the exact `.md`. Those are two fixes in two pushes, not one.

## Arming auto-merge is a readback, not an exit code

`gh pr merge <n> --squash --auto` exits 0 and arms **nothing** when the PR is `mergeable_state=blocked`
(a red required check) — the same silent no-op as a non-default base. A moment after arming, re-read
`gh api repos/<owner>/<repo>/pulls/<n> --jq '.autoMergeRequest'`: `null` means NOT armed. Report
`auto=none (blocked: <the red check>)`, never "armed". A PR with a red check is not done-green and so not
"done" — fix the red or attribute it to another lane's gate first; arming is the trigger, and it only
holds on a PR whose only remaining blocker is the required review.

Three readback states, three different reports — do not collapse them:

- `autoMergeRequest: null` — **not armed**. Report `auto=none`, plus the blocker the board shows
  (`mergeable_state`, the required check that is red or pending).
- `autoMergeRequest` populated (it carries `enabled_by` and `merge_method`) — **an arm request exists and
  the PR is armed.** Report `auto=armed`. Whether it will *actually* merge is a SEPARATE read:
  `mergeable_state` plus the required checks — a red required check leaves it `blocked` and pending, not
  un-armed. **The REST `auto_merge` object has NO `enabled_at` field**, so `.auto_merge.enabled_at` is
  `null` on every PR — never read that null as "not armed", and never accept another lane's "it has no
  `enabled_at`, so it isn't armed": the object's presence (`.auto_merge != null`) IS the arm. The arm
  timestamp lives only in GraphQL (`autoMergeRequest { enabledAt }`), not REST.
- `autoMergeRequest: null` with `mergeable_state: dirty` — **the base advanced into a conflict and GitHub
  disarmed it.** A rebase, a re-push and a fresh `--auto` are required; the previous arm does not survive
  new commits on `main`, so after ANY rebase re-arm and re-read rather than assuming the old arm is still
  armed. The same base advance also invalidates the CI runs already at the old head: their verdicts were
  measured against a base that no longer exists, so they can be green and irrelevant — re-run at the new
  head before quoting them.

## A red `make secret-scan` is a credential SHAPE, often inside a doc example

The `linux / lint` job runs `make lint`, which chains `make secret-scan` → `scripts/secret_scan.py`
(pinned gitleaks image, `.gitleaks.toml`) — a gate that `make ci-lint` alone does not reproduce. A
**documented, illustrative** command can red it: gitleaks' `curl-auth-user` rule fires on a literal
`curl -u "<user>:$(gh auth token)"` shape in a markdown example, so a skill/recipe doc trips
"a committed credential VALUE fails the build" with no real secret present. Fix the ENCODING, not the
intent: switch the example to an env-var form (`GHCR_AUTH="${GHCR_USER}:${GHCR_TOKEN}"; curl -u
"$GHCR_AUTH"`), and apply the identical edit to BOTH the tree copy and the live profile copy so
profile-versioning does not diverge on it.

Reproduce and locate it locally — the CI log is `--redact`ed, so it names no file:

```bash
make secret-scan                    # confirms the red at your head
# gitleaks --report-path must land on a HOST-MOUNTED dir (mount /tmp into the container), else the
# report is written inside the container and lost:
docker run --rm -v "$PWD:/repo" -v /tmp:/out <gitleaks-image> detect --no-git \
  --source /repo --config /repo/.gitleaks.toml --report-path /out/leaks --report-format json
python3 -c "import json;print([f['File'] for f in json.load(open('/tmp/leaks'))])"
```

Then re-run `make secret-scan` and quote "no leaks found" as the fix evidence.

## After a rebase: diff the per-job set between the two heads before attributing a red

The scope selector picks jobs from the diff against the **current base**, so rebasing onto newer `main`
can DISPATCH a job that never ran at the pre-rebase head — an engine diff that got only `scope`/`holds`/
`guard` at the old base can additionally select `linux / unit` at the new base. Two rules follow:

- **A job that never ran is neither green nor red.** Absence at the old head is not a pass you can quote,
  and its red at the new head is not automatically your change. Enumerate the jobs `check-runs`/`jobs`
  at BOTH heads first and mark which job existed at each; only a job present at both, green→red, is a
  candidate regression.
- **A red that was green before is still read at the STEP level.** `linux / unit` is composed (pytest,
  then `ci-unit`'s gate steps); an unticked openspec box reds it there while pytest is green, so a red at
  the new head can be the SAME intended gate re-firing — not a rebase regression. Read the failing step
  (`actions/jobs/<jid> --jq '.steps[]|"\(.number) \(.conclusion) \(.name)"'`) and the pytest summary
  before deciding regression vs the known gate.

## Same cell, same head, different verdict → host-flaky, not a regression

Before treating a cell's red as caused by your commit, compare the SAME cell at a prior run on the same
code path (the same or an equivalent head): if that cell passed `engine-launchers` in run A (reached
`ci-install-uninstall`) and fails the CDI check in run B at the same head, the difference is the runner
host's CDI state, not the code. A fix is "verified" only on the cells a host can actually execute the leg
for: green non-CUDA install-legs (cpu/vulkan/rocm) prove the `~/bin` fix, while a cuda install-leg red on
missing CDI proves the host gap — report both facts separately and attribute each to its owner.

## A quiet local engine build is NOT a hang when the pip/editable stage is mid-compile

A local `make build-engine` can appear frozen for ~2 h while it is genuinely busy: once it reaches the
`uv pip install -e .` stage, the setuptools editable build is a **silent compile stage** (`backend.build_editable`
spawning ninja -> nvcc/gcc/cc1plus/ptxas), and pip/setuptools buffer their output instead of streaming it the way
buildkit's `#N` step lines do. The `docker-buildx` and `uv` processes sit `S`/futex_wait, the log's last line goes
stale, and a tail-only or mtime-only probe reads "STALLED".

Prove liveness by the **compiler processes, not the log**:
`ps -eo pid,cmd | grep -E 'ptxas|nvcc|cc1plus|ninja'`. A live build shows steady multi-core CPU
(roughly `-j N` cores busy) and a **churning PID set** — every finished kernel compile exits and a fresh
nvcc/ptxas appears, so sample the PID set twice ~30 s apart and compare: all-new compiler PIDs = the build is
advancing through kernels. Also read the tree shape (`uv -> backend.build_editable -> cmake --build -j=2 ->
ninja -j 2 -> nvcc/gcc`): `-j 2` is the CUDA `MAX_JOBS=2` cap by design, so a 2-core steady load is exactly
the intended slow path, not a stall. Note the compile object tree lives inside the buildkit container's mount
namespace, so host-side `find` over `/root/.cache` returns nothing — do not use host object counts as liveness.
A genuinely dead build, by contrast, shows zero compiler processes and no CPU for a sustained period, and
fails with a real make error the moment you look. Never report "hung" from a frozen log tail alone.

**Read HOW FAR it has come from the `.cu.o` names on the live nvcc command lines, not from object counts.**
The compile tree and its ninja log live in root-owned namespaces you cannot read non-interactively, so do not
try to count done edges:

- The build runs under `runc --log /var/lib/docker/buildkit/executor/runc-log.json run --bundle
  /var/lib/docker/buildkit/executor/<id> …` — **not** a `docker ps` container, so `docker exec` into it finds
  nothing.
- `/var/lib/docker/buildkit/executor/<id>` and `/proc/<ninja-pid>/cwd` answer **Permission denied** to your
  user, and `sudo` here needs an interactive password (`sudo -n true` → "a password is required"), so the
  precise `wc -l < .ninja_log` fraction is unavailable from an `execute_code` cell. Do not burn calls trying
  to `cat` the ninja log; you will only get sudo-password errors.
- Extract the exact kernels in flight instead: `ps -eo cmd | grep nvcc | grep -v grep | grep -oE
  '[a-zA-Z0-9_]+\.cu\.o$' | sort -u`. The names (`flash_fwd_hdim192_fp16_sm80.cu.o`,
  `flash_fwd_split_align_hdim256_bf16_causal_sm80.cu.o`, …) tell you which flash-attn hdim/phase/arch the build
  has reached, which is the honest "how far" answer.
- **A 30 s sampler that shows 0 kernels finished and 0 new is NOT a stall** when the two largest kernels
  (hdim256 / split-align, minutes each under `-j 2`) occupy the whole window. Sample kernel-set twice ~30–60 s
  apart and read the ADVANCE (hdim192+hdim256 mixing phases → both split-align) — monotonic kernel-advance, not
  finished-in-30s, is the progress signal. Same lesson as the PID-churn test, applied to the kernel roster
  instead of the PIDs.
- When the user asks "how far has it come", give the current kernel names + elapsed + which extension group is
  compiling (e.g. `_vllm_fa2_C` flash-attn leg) and a rough remaining estimate, and say the exact edge-count
  needs a root shell — never invent a done/total fraction you could not read.

## An owner "kill all CI" directive cancels EVERY in-flight run — enumerate across all workflows

An owner directive to stop / kill the CI is an explicit override of the lane's "never cancel a live run"
default and must be executed immediately — but cancel only what the enumeration finds, and enumerate ALL
workflows, not just the one you were watching. A wedged trigger lives in `engine-build-pr-trigger.yml`,
while `ci.yml` and `engine-build.yml` hold separate run ids; cancelling only "your" ci run leaves the
trigger still holding its per-PR concurrency group, so nothing is really stopped.

    for wf in ci.yml engine-build.yml engine-build-pr-trigger.yml; do
      gh run list -R asimov-agent/llgenie --workflow=$wf --limit 15 \
        --json status,databaseId,headSha \
        --jq '.[]|select(.status=="in_progress" or .status=="queued" or .status=="pending")|[.databaseId,.status,.headSha[0:8]]|@tsv'
    done
    # then: gh run cancel <id>   for each id returned

- **The status filter must include `pending` AND `queued` AND `in_progress`.** A run wedged in a
  concurrency group reads `pending`; filtering on `in_progress` alone misses exactly the stuck trigger you
  are trying to clear, and you report "all stopped" while it still holds the group.
- **`gh run cancel` on a run stuck inside a `make …` await step can take up to a minute to land** — the
  cancel request does not kill the in-flight `make` subprocess instantly. Poll `gh run view <id> --json
  status` until it reads `completed`; do not report a run cancelled while it still reads `in_progress`.
- **Verify with a SECOND enumeration after a short wait that returns ZERO rows** across all workflows —
  "I submitted cancels" is not "nothing is running". Quote the empty second read as the stopped evidence.
- **Kill any local watcher loops you armed in the same move** (`pkill -f 'watch-'`); the `pgrep` that runs
  the kill command matches its own shell, so ignore that one self-match rather than reading it as a live
  watcher.
