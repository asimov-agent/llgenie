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
