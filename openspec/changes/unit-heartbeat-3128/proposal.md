# Unit suite progress heartbeat (#3128)

## Why

A healthy 23m51s pytest phase read as a wedged run because no job-log line appeared between step start and suite completion (run `46142262014`, job `140970673262`).

## What changes

`scripts/unit_tests.py` polls its pytest child with `Popen.wait(timeout=...)` and emits a timestamped heartbeat at a bounded interval. The 120-minute job ceiling is unchanged.

## Capabilities

- Progress lines in the unit job log while pytest is running.
- A bounded, replayable cadence with an environment override.

## Impact

Monitors can distinguish a progressing unit job from a wedged one from the job log alone, without waiting for a step boundary or cancelling a live run.
