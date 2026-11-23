# 2026-11-23 — monitor wrapper: a failed clone refresh is now its own alarm (issue #3016)

## What was verified against the issue

- The measured blindness reproduced in code review and fixed: the host wrapper ran
  `git fetch origin main` and `git merge --ff-only origin/main` with ignored exit statuses and
  returned silently on a dirty tree; every broken refresh then fell through to `make -s ci-monitor`
  on a stale clone and printed `MONITOR-ERROR make-ci-monitor-failed` — the exact line the tick
  contract reads as "the target is not on main yet: do nothing". The clone sat on
  `786239627c1a` for ~12 h (reflog to `fde44d146`) while PR #3014 had merged at 07:34Z.
- `scripts/host_ci_monitor_wrapper.py` is now the repo-canonical wrapper (the host copies were
  hand-written and covered by no gate). `_ensure_clone()` returns `(ok, detail)` for clone/fetch/
  merge failures and a dirty tree; `main()` prints the distinct stable line
  `MONITOR-ERROR clone-refresh-failed` (detail on stderr) and never calls `make` on a clone it
  cannot trust. `MONITOR-ERROR make-ci-monitor-failed` is now emitted only for a genuine make
  failure on a refreshed, clean clone — the honest "not landed" line keeps its meaning.
- Second gap closed: make's stderr is passed through in every outcome, so the spec'd
  `MONITOR-ERROR gh-fetch-failed` detail (a stderr line from `scripts/ci_monitor.py`) finally
  reaches the cron log even when make exits 0.
- Tests (`tests/test_host_ci_monitor_wrapper.py`, 5, hermetic — local-path git remotes, fake
  Makefiles, zero network): fetch-fail → refresh line only; dirty clone → refresh line only;
  clean+current clone whose Makefile lacks the rule → still `make-ci-monitor-failed`, no false
  refresh alarm; green run → stdout passthrough; green run with make stderr → stderr passthrough.
  `pytest … -q` rc=0 (5 passed); `make lint` rc=0; `make check-wiring` rc=0 (492 documents).
- Host install verified: `make host-ci-monitor-install` rc=0 — repo copy, `~/.hermes/scripts/` and
  both profile script copies share one sha256 (`57a082c4…`); monitor clone refreshed to
  `bc75f93fa` == `origin/main`, clean; a live wrapper run rc=0 printed the 13-line incident
  snapshot with empty stderr.
- The live cron job (`857ee38c40ce`, profile `llgenie-planner`) prompt was rewritten: the refresh
  line is an alarm (check the clone, restore the refresh path, do not idle), and
  `make-ci-monitor-failed` means "not landed" only when the clone is current. The repo mirror of
  that prompt (`agents/llgenie-planner/prompts/llgenie-ci-monitor.md`, PR #3023) carries the same
  wording (`c4b2a391a`).

## Decisions

- The wrapper lives in the repo and the host files are installed mirrors via
  `make host-ci-monitor-install` — "in the llgenie repo" with a gate, no hand-edited host copies.
- One distinct line per failure class (byte-stable stdout) rather than collapsing everything into
  the not-landed line: the cron's hash gate needs one stable state per state class.
- Hermetic git fixtures instead of the issue's live-clone repros (Repro A/B), so `make test-unit`
  covers all three states forever.

## Current status

Branch `feat/monitor-clone-refresh-detect` in its own worktree; OpenSpec change
`monitor-clone-refresh-detect` (T1–T5 ticked, verification task pending full battery + preflight).
Host already runs the hardened wrapper; the PR ships the repo-side contract.
