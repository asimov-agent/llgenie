# issue-dedupe-jev-preflight — proposal

Issue: [#802](https://github.com/asimov-agent/llgenie/issues/802)

## Why

The duplicate sweep stopped sweeping at 13:34Z on 2026-10-28 and every run since died at the same step.

Measured on `asimov-agent/llgenie`:

| run | time | conclusion | failing step |
|---|---|---|---|
| 40697636784 | 13:34:15Z | failure | `dedup :: Prove the JEV engine is active — the decision does not start without it` |
| 40702295009 | 14:04:02Z | failure | same step |
| 40643207518 | 06:20:04Z | success | the JEV step was **skipped** (no pair was picked) |

`gh run view 40702295009 --log-failed` gives the cause in one line:

```
[require-env] FATAL: TYPESAFE_API_KEY is missing or empty — refusing to start.
make: *** [Makefile:661: agent-jev-preflight] Error 2
```

`issue-dedupe.yml`'s `dedup` job sets `NOUS_API_KEY` and `REPO` and nothing else, while the step it runs
(`make agent-jev-preflight NERVE_REQUIRE=1`) refuses to start without `TYPESAFE_API_KEY` (the guard from
#363 in front of the leg). The job had never reached that step before: the 06:20 run picked no pair, so
the step was skipped and the missing secret stayed invisible. The first run that actually had a pair to
compare failed in its preflight and decided nothing — and `gh issue list --search 'JEV'` found no
tracker, so the failure had no work item at all.

## What Changes

- **`.github/workflows/issue-dedupe.yml`**: the `dedup` job passes `TYPESAFE_API_KEY` from the repo
  secret (run time only, like every other bot job), and the preflight step runs the new target instead
  of the bare one.
- **`Makefile` (`issue-dedup`)**: the leg's container now forwards `-e TYPESAFE_API_KEY`, exactly as
  `issue-refiner` does — the job-level secret reached only the host step, so the decision leg itself
  would still have run with the layer off.
- **`make jev-preflight-required`** (`REPO=`, `RUN_URL=`, `DRY=1`): runs the same preflight, keeps its
  exit status (the step stays red), and on failure prints the failure **class**, the measured line and
  the fix for that class, then files ONE tracker issue per class.
- **`scripts/jev_preflight_tracker.py`**: the classifier + the tracker. Nine classes read from the
  preflight's own words (`key-missing`, `plugin-missing`, `plugin-disabled`, `hermes-missing`,
  `smoke-missing`, `provider-unsupported`, `provider-no-payload`, `provider-unreachable`, `unknown`),
  a body rendered by `scripts/issue_body.py` (registered as a producer), and a dedupe marker
  `<!-- jev-preflight: <class> -->` as the body's first line. A second failure of the same class finds
  the open issue and files nothing — once per class, not once per run.
- **`tests/test_jev_preflight_tracker.py`** in `make test-unit`: the classifier against the real
  preflight strings, the first-failure issue, the per-class dedupe, two classes → two trackers, the
  unset-repo and gh-failure loudness, and the workflow wiring (the key reaches the step; the step runs
  the tracking target).

## Impact

- The sweep either runs or says why not in one readable place: the run's output names the class and its
  fix, and the issue list carries exactly one open work item per class.
- A missing provider secret in a bot job can no longer hide behind a step name — the first picked pair
  surfaces it as `key-missing` with the exact wiring to add.
- Not covered, filed separately: the refiner's 3/day budget (#547) and the sweep's blindness to the
  accumulating duplicate class (#563).
