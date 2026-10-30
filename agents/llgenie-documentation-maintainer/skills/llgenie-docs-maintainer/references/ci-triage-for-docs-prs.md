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
| one job `in_progress` far past its measured duration (see below), and it has no `timeout-minutes` | hang | owner decides; cancel the run, then `gh run rerun <id> --job <jobId>`; tell the fleet first |
| `check_pr_authors` red on a commit you did not write | base branch | name the sha and its owner; never re-author another lane's history |
| `linux / unit` red on a real unit test | genuine | reproduce in the repo's test image before touching anything |

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
