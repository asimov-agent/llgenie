# Make a stuck runner loud instead of an eternal `pending`

## Why

A job whose runner label matches nothing does not fail — GitHub leaves it `queued` forever. The
run never concludes, `mergeStateStatus` stays `BLOCKED`, and every PR's checks show "pending"
with no signal anywhere: main's runs have been stuck since 04:22 on the `macos` jobs (labels
`macos-15-intel`, `runner=(none)`), which is the state reported in #254.

The cause has two candidates (a self-hosted runner offline/unregistered, or hosted macOS
minutes/spending exhausted) and both are a maintainer decision — but the *silence* is not: a
stuck queue should be visible within half an hour, with the label named, so the fix is obvious
and nobody re-diagnoses it from scratch.

## What Changes

- **`scripts/queued_run_alarm.py`**: inspect a repo's in-progress runs, list the jobs still
  `queued`, and report the ones queued longer than `--minutes` (default 30) with their age,
  workflow, branch, run and **runner label**; explain what a matched-nothing label means; and
  point at #254. Exit 0 clean, 1 stuck (so a scheduled run goes red), 2 GitHub unreachable.
  `--comment` posts ONE comment per affected run, deduplicated by its own marker, so a sweep
  twice an hour cannot spam.
- **`.github/workflows/queued-alarm.yml`**: `schedule` twice an hour + `workflow_dispatch`, with
  no conditional job (issue #107 requires the decision to live in code, and it does).

## Impact

- Read-only apart from the optional comment; no secrets in files (the PAT arrives as `GH_TOKEN`).
- This does not fix the runner — it makes the failure loud, names the label, and gives the
  maintainer the two facts that decide the fix. It is the option #254 lists as implementable
  regardless of the cause.
