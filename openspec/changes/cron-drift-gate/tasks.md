# Tasks

- [x] Write `scripts/check_cron_drift.py` (two-job table, $HOME not absolute)
- [x] Wire `make check-cron-drift` (LIVE=; ROOT=) beside check-tick-prompt
- [x] Hermetic tests (fails-on-drift, passes-when-synced, missing-versioned, missing-live)
- [x] Prove on real live bytes: rc=0 synced, rc=1 on drift
- [x] Change-note trio + openspec
