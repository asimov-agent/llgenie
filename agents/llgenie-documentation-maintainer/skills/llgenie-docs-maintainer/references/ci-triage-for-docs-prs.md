# Triaging CI on a documentation-only PR

A docs PR touches `docs/**`, `agent-wiki/**`, `docs/changes.d/**`, `CHANGES.md` or `agents/<profile>/`
— no code, no data. That makes most red jobs someone else's, and the triage is about proving it without
cancelling matrices or pushing noise.

## Order

1. `gh pr view <n> --json state,mergedAt,headRefOid` — history vs work; a merged PR's run is history.
2. `gh run view <id> --json jobs --jq '[.jobs[]|select(.conclusion!="success" and .conclusion!="skipped")|{n:.name,c:.conclusion}]'`
   — one named job, or many cancelled at scattered timestamps (a sweep).
3. Read the log by **job**, not by run (`gh run view --log` serves nothing until the run completes):
   `gh run view --repo <r> --job <jobId> --log | grep -aB4 '<target>'`.
4. Classify before acting:

| symptom | class | action |
|---|---|---|
| gate over `data/` or the live registry: `fixture is stale`, link/advisory counts | live-data drift | run that gate locally at the same head; if it passes, comment both outputs and `gh run rerun <id> --failed` |
| `guard` never starts, `0/N` jobs, dozens `queued` repo-wide | capacity | report to the fleet; rerun/cancel/dispatch only adds to the queue |
| several jobs cancelled within seconds, earlier ones green | fleet sweep | `gh api …/actions/runs?head_sha=<sha>`; nothing newer exists = rerun at the same head |
| `linux / unit` cancelled at ~1h with repeated `Timeout (0:05:00)!` in its step log, while every sibling job of the same run is green | runner starvation of the long job | `gh run rerun <id> --failed` at the same head; if the same signature repeats, wait for a quiet window rather than rerun-looping |
| `linux / unit` cancelled at only ~25-30 min, siblings green, base already on the new ceiling, workflow has NO `concurrency:` block, run's `head_sha` is a superseded head | superseded-head cancel (owner/API) | nothing to rerun; confirm no run at the *current* head is in flight, then push the next head; report as *not classified* |
| one job `in_progress` far past its measured duration (see below), and it has no `timeout-minutes` | hang | owner decides; cancel the run, then `gh run rerun <id> --job <jobId>`; tell the fleet first |
| `check_pr_authors` red on a commit you did not write | base branch | name the sha and its owner; never re-author another lane's history |
| `linux / unit` red on a real unit test | genuine | reproduce in the repo's test image before touching anything |

## The ~1h `ci-unit` cancellation fingerprint

The long unit step can be killed by the runner without any test failing, and the log reads like a
timeout of the suite:

```
linux / unit  UNKNOWN STEP  ... Timeout (0:05:00)!
linux / unit  UNKNOWN STEP  ... Timeout (0:05:00)!
linux / unit  UNKNOWN STEP  ... ##[error]The operation was canceled.
```

Recognise it by three facts together, because any one alone is ambiguous: the captured step is
`make ci-unit`, the cancellations are spaced tens of minutes apart, and **every other job in the same
run is `success`** (guard, lint, install, top-level, openspec). A genuinely red test would fail with a
pytest traceback, not with a watchdog line. `gh pr checks` renders this job as `fail`; the job's own
`conclusion` is `cancelled`.

- Diagnose with `gh run view <id> --json jobs --jq '.jobs[]|{name,conclusion,steps:[.steps[]|select(.conclusion!="success")|.name]}'`
  — the cancelled job names the one step that never completed.
- Recover with `gh run rerun <id> --failed` (reruns the failed/cancelled jobs only, reusing the same run
  and the same head) — never a push, never an empty commit.
- A rerun inside the same congestion window can produce the identical signature. Two identical
  cancellations mean the window, not the diff: stop, report it, and re-run when a sibling run at some
  head shows `ci-unit` succeeding. The run's own log cannot tell you the runner was starved; another
  run's success at a later time can.
- While a rerun is in flight `gh pr view --json mergeable,mergeStateStatus` answers `UNKNOWN`; that is
  churn, not a conflict. Re-read after the run concludes before writing anything about its state.

## The `check-import-roots` ratchet red

`check-import-roots` (Makefile `ci-unit`, issue #796) is a **ratchet**: it records offender counts in
`tests/fixtures/import-roots-baseline.json` (`bare` / `sys-path`) and exits 1 the moment a count RISES.
A docs or gate PR that adds a test which inserts its own `sys.path` or imports a `scripts/` module bare
reds `ci-unit` with `Makefile:402: check-import-roots Error 1` — and the site named in the log may be an
**old** offender (`tests/test_engine_runner_failfast.py:21` is a well-known one), because the check
lists every site, not only the new one. Key facts:

- Baseline is a measurement: `bare`/`sys-path` may fall, never rise. A new offender is a **code fix in
  the PR** (`from scripts import check_docs` via the conftest seam — see `tests/test_check_docs.py`),
  never a fixture bump.
- Diagnose/verify on the branch before pushing, and capture the exit correctly:
  `python3 scripts/check_import_roots.py ratchet; echo ${PIPESTATUS[0]}` — `$?` after a pipe reads the
  last stage, which lies.
- The fix is exempt from the change→note gate (#1123): it changes only a test file.

## The old-ceiling cancel (merge-ref evaluation)

A `pull_request` workflow run is evaluated at the **merge ref** (head merged into base), i.e. the
workflow YAML comes from the base unless the PR itself changed it. So a CI-ceiling raise merged on
`main` does **not** apply to an unrebased PR: its runs are still judged by the OLD ceiling text.

- **Fingerprint:** `linux / unit` `completed/cancelled` at ~the old ceiling (60 min) with **zero test
  output** (the `make ci-unit` step shows `cancelled`, no failure log) while every sibling — `install`,
  `lint`, `cpu-health`, guard/holds — is green, and no newer run exists at the head (not a respawn).
- **First check before any action:** `gh pr view <n> --json baseRefOid` vs the ceiling-merge sha on
  main (`git fetch origin refs/heads/main:refs/remotes/origin/main && git log --oneline
  origin/main -- .github/workflows/pipeline.yml | head`, or the planner's relay). If the base is an
  ancestor of the ceiling merge and the PR does not touch `pipeline.yml`, the cancel is the
  old-ceiling fingerprint — neither a code defect (like the ratchet red) nor necessarily a starved
  runner.
- **Recovery:** rebase onto the fresh `main` and force-push with lease (own branch), so the fresh run
  evaluates at the new ceiling; then re-judge. Do **not** `gh run rerun` a run doomed by the old
  ceiling: it replays the recorded 60 and lands a second identical cancel that reads as starvation on
  the ledger. If you already reran by mistake, cancel your own doomed rerun (documented) rather than
  feed the ledger another copy.
- Re-evaluate after the fresh run: a 120-budget cancel at ~1h is the real starved-runner signal and
  goes to the queue-shaping ledger (#882/#1146/#1139), not to another rerun loop.

## A `base..HEAD` gate red that cites FOREIGN issue numbers is base-staleness, not your diff

`check-pr-closing` (and `scope`) read the commit range on the **merge ref** — GitHub merges your
branch into the *current* base tip, so the range is `base-tip..merge`, not `your-base..your-head`.
When your branch is based on an older `main` and the base tip has advanced (other PRs merged),
that range **includes main's own newer commits**. Their messages carry their own `closes #<n>` and
`(#<m>)` claims, so the gate reports a mismatch — "joined commits close #1398, #1514; body closes
#1398", or "commits claim #1524 and don't close it" — with **ids that are not in your own log**.

- **Fingerprint:** the guard names issue numbers you never touched; `git log --oneline
  origin/main..HEAD` shows ONLY your commits; the PR body closes exactly the issue you meant. That
  contradiction IS the diagnosis — the foreign ids come from main advancing under an unrebased base.
- **Fix (the #1015 stale-base case — rebase is warranted here, the gate genuinely reds):** fetch
  fresh (`git fetch origin +refs/heads/main:refs/remotes/origin/main`), `git rebase origin/main`,
  re-apply the same commits (content unchanged), verify `origin/main..HEAD` is now only your
  commits, then `check_pr_closing.py check --body-file <body-with-closes> --base origin/main --rev
  HEAD` returns 0, and `git push --force-with-lease` (own branch, fetched immediately before).
- Same artifact reds `scope`/`ci-verdict` at that head (foreign commits in the ranged diff) — no
  scope defect to investigate. Never weaken the gate or edit commit messages to hide it; rebase.

## Running one gate test when the suite harness will not start

Not every cancel is the old ceiling or starvation. A `completed/cancelled` whose long job dies well
**before** any ceiling (~25-30 min of a ~1h45 job), with every sibling green and no failure anywhere,
is a separate class — usually an owner/API cancel of a run at a **superseded** head (one that was never
going to be the merge verdict), taken to free the runner.

Discriminating facts, all cheap to read:

```bash
gh api repos/asimov-agent/llgenie/actions/runs/<id> --jq '{name,created_at,updated_at,head_sha:.head_sha[0:7],actor:.actor.login,triggering_actor:.triggering_actor.login}'
gh api repos/asimov-agent/llgenie/actions/runs/<id>/jobs --jq '.jobs[]|"\(.name) \(.conclusion) \(.started_at) \(.completed_at)"'
git show <base>:.github/workflows/pipeline.yml | grep -n -A5 concurrency   # no match = no cancel-in-progress
```

- **Duration rules it out of both known classes:** the ~1h45 job ending at ~27 min is neither a
  ceiling hit nor a starvation watchdog.
- **No `concurrency:` block** at the base means no newer run could have cancelled it by the usual
  mechanism — so the cancel came from an actor, not from a push.
- **`head_sha` != the PR's current head** means the run was already superseded: its verdict could never
  be the merge verdict, so there is nothing to rerun and nothing to fix in the diff.
- **Report it as *unclassified*, with the measurements.** Never file "too short, wrong shape" cancels
  into the starvation ledger — a polluted ledger makes the real capacity signal unreadable. State the
  facts, state which classes it is *not*, and leave the classification to the ledger's owner.
- **A leftover `in_progress` run at an OLD head does not block a push.** Before deferring a push because
  "a run is in flight", read the run's `head_sha`:
  `gh api "repos/<r>/actions/runs?status=in_progress" --jq '[.workflow_runs[]|select(.head_branch=="<branch>")|{id,head:(.head_sha[0:7])}]'`
  — a run pinned two commits behind cannot be destroyed by pushing the current head, so the push window
  is open.

## A post-merge `failure` at a superseded head is a head-instance red — classify per test

An owner/planner merge can land while `linux / unit` is still `in_progress`, so a watcher on that run
returns `failure` **after** the merge. That verdict is about a head nobody owns any more: it is neither
"CI failed" nor "CI green", and reporting either is a claim about a branch that no longer exists.
Enumerate the failing test ids from the run
(`gh api repos/<r>/actions/runs/<id>/jobs --jq '.jobs[]|select(.conclusion=="failure")|.name'`, then the
job log's `FAILED tests/…` lines) and re-judge each one **at merged `main`**, per test:

- A doc-gate red whose whole content is a **count** (`289 vs 291 targets`) re-run at merged `main` and
  passing there is head-instance: the merge commit's re-run clears on identical content. That is the
  documented latitude for a merged fold — say "head-instance red, merged-main green", with both shas.
- A **live-data / image-publish** test in the same failure set (e.g. a registry `404` on a published
  image) is someone else's lane by construction; naming it keeps the classification from reading as
  "my diff is fine because I only checked the one test I care about".
- Report the set, the per-test re-judgement and the main sha — never a bare "the run failed".

## Running one gate test when the suite harness will not start

Symptom in a scratch venv: `python -m pytest tests/test_check_docs.py -q` exits **2** with a **0-byte**
output file. Exit 2 with no output is a startup/collection failure (conftest/env or a missing import),
not a test result — and `| tail` / `| head` hand back nothing while `$?` reads the last stage of the
pipe, so both the code and the output lie. Redirect to a file and read it back; use `${PIPESTATUS[0]}`
if you must pipe.

Get a real verdict by calling the test function directly, bypassing conftest/plugin startup:

```bash
python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('t','tests/test_check_docs.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
getattr(m,'test_the_real_tree_documents_every_user_facing_target')()
print('PASS t')"
```

- A `ModuleNotFoundError` at `exec_module` (e.g. `yaml`) is a **missing scratch dependency**, not a
test defect — `pip install pyyaml` in the venv and re-run. Do not report it as a gate failure.
- The test reads the repo root from its modules (`REPO`), so run it with the worktree as cwd.
- **`--noconftest` + an empty HOME reproduces CI when the conftest consumes argv at import time.**
  If `python -m pytest <file> -q` swallows output and exits 2 because `conftest.py` imports a module
  that reads `sys.argv` at import (a host-venv quirk CI avoids by running containerized), run the
  selected tests with `--noconftest` and a synthetic empty HOME so the live-parity comparison is
  skipped exactly as CI skips it:
  `env -i HOME=/tmp/nonexistent-ci-home PATH="$VENV/bin:/usr/bin:/bin" $VENV/bin/python -m pytest
  tests/test_<x>.py::<test_name> -q --noconftest -p no:cacheprovider --no-header`.
  A `findings(...)==[]` assertion that fails only with a non-empty HOME is the host-only live-parity
  drift (live-edited-not-tree / absent-from-tree keys), not a defect your change introduced.

## How long the long jobs actually take

Calibrate before calling anything hung: a wrong "stalled" call costs a re-run of a ~1h45 matrix.

- **`linux / unit` is a ~1h45 job.** `make test-unit` alone measures ~1h31 over ~14,500 tests; the whole
  step lands near 1:45, and the slowest green observed was 1:45:46. Thirty or sixty minutes in is **on
  schedule**, not a hang; suspicion starts near 1h50.
- **Read the job's `startedAt`, not the wall clock:**
  `gh run view <id> --json jobs --jq '.jobs[]|select(.name=="linux / unit")|{s:.status,started:.startedAt}'`.
  A queued run inflates the number you are reasoning about without a single step having executed.
- **A missing `timeout-minutes` is the actual defect.** `pipeline.yml`'s `unit` job declares none, so
  GitHub's 6-hour default applies and a real hang is invisible instead of failing with a log. Any
  ceiling proposed for that job must be **≥150 minutes**: a 60-minute ceiling reds a *passing* run,
  which is worse than having none.

## Local evidence, in the image CI uses

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo llgenie/test:latest \
  python -m pytest tests/test_check_docs.py tests/test_wiring.py tests/test_architecture_bot.py \
  -p no:cacheprovider -q --tb=short          # the files a doc change actually touches
NERDCTL=docker make test-unit                # whole discovered suite (~10+ min, can die partway)
```

Quote pass counts verbatim; a partial run is reported as partial, never rounded up to "suite green".
Local green is **evidence, not the gate** — the landing grant needs a green run at the head.

## Never

- Push an empty commit to manufacture a fresh run: it moves the head and voids a grant pinned to a sha.
- Push while any job at the head is `in_progress` (`cancel-in-progress` makes it destructive; a
  queued-only run is safe to supersede).
- Rerun-loop the same live-data or capacity failure: two identical reds mean the fix is upstream.
