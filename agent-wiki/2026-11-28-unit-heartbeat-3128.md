# Unit heartbeat: a slow suite is not a wedged run (#3128)

`linux / unit` spent 23m51s in one `pytest` invocation on PR #3125 (run `46142262014`, job `140970673262`). The job was healthy — `4570 passed, 13638 deselected in 1431.49s` — but run-level `updatedAt` stayed frozen and the mid-run job-log endpoint answered `BlobNotFound`, so monitors had no way to tell progress from a hang.

`scripts/unit_tests.py` now runs the child with `Popen` instead of `subprocess.call` and polls with `wait(timeout=...)`. Every interval it prints `[unit-suite] heartbeat +Ns (0:00:NN) pytest still running (pid P) — progressing, not wedged` to the job log with inherited stdio. Default cadence is 300 seconds; `UNIT_HEARTBEAT_SECONDS` shortens it for replay and is clamped to at least one second.

This is a progress signal only. The 120-minute job ceiling in `.github/workflows/pipeline.yml` is untouched, no live run is cancelled, and the child's exit code is returned unchanged.
