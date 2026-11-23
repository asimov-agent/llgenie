# monitor-clone-refresh-detect

## Why

Issue #3016: the sanctioned host CI monitor's wrapper (`~/.hermes/scripts/llgenie_ci_monitor.py`,
the `--monitor-script` of the `llgenie-ci-monitor` cron job) refreshes a dedicated clone
(`~/.hermes/checkouts/llgenie-main`) and runs `make -s ci-monitor` there — but it ignores the exit
status of `git fetch origin main` and `git merge --ff-only origin/main`, and returns early on a dirty
tree without reporting anything. Every one of those broken states falls through to `make` on a stale
tree and prints the single stable line `MONITOR-ERROR make-ci-monitor-failed` — the exact line the
tick contract reads as "the monitor target has not landed yet: do nothing this tick". Measured
2026-11-23: the clone sat at `786239627c1a` for ~12 hours while `origin/main` already carried the
target (PR #3014 merged 07:34Z); every tick in that window read as a calm board. A control whose
failure is indistinguishable from its absence is a control that does not exist. The wrapper also has
no repo home: it exists only as two host copies, so no gate or test covers it.

## What Changes

1. Give the wrapper a repo home: `scripts/host_ci_monitor_wrapper.py` is the canonical copy;
   `make host-ci-monitor-install` copies it byte-identical to the host paths
   (`~/.hermes/scripts/` and the profile `scripts/` dirs). The host copies become mirrors, not sources.
2. `_ensure_clone()` checks return codes: a failed `clone`, `fetch`, or `merge --ff-only`, and a dirty
   tree, each take a distinct stable stdout line `MONITOR-ERROR clone-refresh-failed` (detail on
   stderr) instead of falling through to `make`. `MONITOR-ERROR make-ci-monitor-failed` then means
   only what it claims: make itself failed on a refreshed clone.
3. Close the stderr gap: when make exits 0, the wrapper passes `make`'s stderr through, so
   `scripts/ci_monitor.py`'s `MONITOR-ERROR gh-fetch-failed` detail reaches the cron's stderr.
4. Hermetic tests wired into `make test-unit` drive all three states (refresh failed, dirty clone,
   genuinely pre-target clone still printing `make-ci-monitor-failed`) with local git remotes and a
   fake Makefile — zero network.
5. The tick contract's carve-out narrows: `make-ci-monitor-failed` means "not landed" only when the
   clone is at or before the commit that added the target; `clone-refresh-failed` is an alarm the
   agent must act on, not idle through (live cron prompt + repo prompt mirror updated).

## Impact

- Affected specs: `host-ci-monitor` (ADDED requirements: wrapper clone-refresh detection, stderr
  passthrough, repo-canonical wrapper with install target, hermetic state tests).
- Affected code: new `scripts/host_ci_monitor_wrapper.py`, new `tests/test_host_ci_monitor_wrapper.py`,
  `mk/bots.mk` (`host-ci-monitor-install`), `Makefile` `.PHONY`, host copies (install target output).
- Host plumbing (not in the diff): cron job prompt carve-out update; clone + live copies re-installed.
