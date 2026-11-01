# Measuring a job's duration band (slow vs stuck)

When the ask is "is this leg slow, or hung?", the deliverable is a distribution of **completed job
durations**, not one run's wall clock and not the number an issue quotes. A single number cannot tell
slow from stuck, and a number sampled during a concurrency spike is not a band.

## 1. Build the band from JOBS, not runs

Take `started_at → completed_at` of the **job** (the job name has spaces: `linux / unit`), never the
run's `created_at → updated_at` — the run window spans install/compile time and any inter-attempt gap
(see `references/diagnosing-cancelled-runs.md`).

```
gh api "repos/<o>/<r>/actions/runs?branch=main&per_page=40" \
  --jq '.workflow_runs[]|select(.name=="CI" and .conclusion=="success")|.id' | while read id; do
    gh api "repos/<o>/<r>/actions/runs/$id/jobs" \
      --jq --arg id "$id" '.jobs[]|select(.name=="linux / unit")|"\($id) \(.started_at)→\(.completed_at)"'
done
```

Report **p50 / p95 / min / max and the run ids** — a p95 with no ids is not reproducible. Exclude
`cancelled` and `skipped` jobs: they have no duration to contribute, and including them silently
lowers the band (a superseded 18-second attempt is not fast CI).

Note: `/actions/runs/<id>/jobs` concatenated by `--paginate` is **not** one JSON document — parse with
`--jq` per call (as above) or write each page to a file; `json.loads` over paginated output fails.

## 2. Re-measure any duration an issue asserts, and name the window

An issue's "this leg takes 40–60 min" is a claim about the instant it was sampled. Before building a
fix on it, check whether that sample sat inside a **concurrency / runner-starvation window** (several
matrices on the same runner family, a backfill of re-runs, a cancelled-and-refired burst). The same leg
measures ~12 min p95 in steady state and 40–60 min during such a window — the artifact, not the code,
is the difference. State the window and the heads the band was measured across, then say plainly which
figure is current.

## 3. Locate the dominant step before proposing a fix

`gh run view <run-id> --json jobs` gives per-step start/complete times. The step that owns ~all of the
wall (measured: `make ci-unit` at 98%, with setup/checkout/docker/test-env under 0.2 min) is the only
one worth acting on. A fix aimed at a 2%-step is noise.

## 4. Measure the heaviest test file hermetically; never extrapolate

A per-case duration multiplied by case count is wrong by an order of magnitude when the per-case number
came from a cold or non-hermetic run. Collect, then time the file itself in the repo container:

```
/bin/sh -c 's=$(date +%s); python -m pytest tests/<file>.py -q 2>&1 | tail -3; e=$(date +%s); echo "WALL=$((e-s))"'
```

`/bin/sh` has no `time` keyword — use `date +%s` and subtract. A python container run as root writes
`__pycache__` into the bind mount and can fail the next compile check on permission; set
`PYTHONPYCACHEPREFIX=/tmp/<dir>` on the `docker run` to keep the tree writable.

**Match the real gate's marker deselection, or your ranking is of a different suite.** `make test-unit`
selects with `-m "not network"`; a bare `pytest tests/` run does not, so it times the live-fetch tests
the gate skips and puts them at the top of `--durations=0` — an inflated, wrong ranking. Read the real
invocation out of the CI job log (`make ci-unit` step) or `scripts/unit_tests.py argv`, confirm the
`-m "not network"` seam is present, and quote it in the report. Build from a checkout at current
`main` tip: a stale worktree predating the seam silently omits it. Sanity check: the run's
deselected count (`~12000+`) should show the network tests were excluded.

## 5. Report the floor, so lanes stop re-running live jobs

Set "slow vs stuck" at **~2× p95**: below it the leg is working and a re-run only burns a runner;
above it with no conclusion (and no test summary in the log) it is a hang. Post the band, the dominant
step, the heaviest file's measured wall, and the floor — that is the whole answer.

## 6. A measurement issue can close with no PR — unless it refutes a documented claim

An acceptance that asks for p50/p95, the dominant step and a recommendation is satisfied by evidence
comments. "The band is fine; the fix is scheduling, not code" is a correct, complete answer — do not
manufacture a code change to look productive, and do not open a fix PR whose diff nobody asked for.

**The exception is the whole point of the measurement when it contradicts the tree.** If the measured
band refutes a figure the repo *asserts* (a docstring/Makefile/`agent-wiki` note that says "30+
minutes" when the band is ~12), then correcting that claim IS the legitimate task-relative change —
it is not "manufacturing" a diff, it is the defect your lane exists to catch ("documented only when
the doc and the measurement agree"). Grep the tree for the old figure (`git grep '30+ minutes'`,
`git grep '40.60 min'`), fix every `file:line` that carries it, add the change→note, and ship it as
the PR. Routing around a disproved doc as "report-only, no code needed" is the failure: a green
board that still tells every future reader a false number is not a delivered measurement.
