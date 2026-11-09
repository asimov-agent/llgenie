# Reading a `ci-unit` red on a bot PR — the aggregate bucket is the least informative signal

Two `linux / unit` reds on one security PR (#1876 / issue #1282, 2026-11-06) had the SAME aggregate signature
(`make ci-unit` step failed, other matrix legs green) but DIFFERENT causes — and neither was a test failure.
Read the failing job's OWN log (`gh api .../actions/jobs/<id>/logs`) before concluding anything, and name the
gate/script the log points at, never the bucket.

## Cause 1: `check-proc-gate` — a bare subprocess call site in a NEW scripts/ module

`check-proc-gate` (issue #797) confines every `subprocess.(run|check_output|Popen)(` call in `scripts/` to
`scripts/proc.py` or a `# proc-allow:` line. A new `scripts/engine_pins.py` used a bare
`subprocess.run(["git", "rev-parse", "HEAD"])` for its head-sha probe.

Correct fix: route through `scripts.proc.run_ok` (never raises on non-zero, caller inspects `returncode`) — NOT a
`# proc-allow:` carve. Two traps:

- A top-of-module `from scripts.proc import run_ok` FAILS under plain `python3 scripts/x.py` (only `scripts/` is
  on `sys.path`, not the repo root). Insert the repo root into `sys.path` first — same pattern as
  `scripts/check_pr_acceptance.py` (`REPO_ROOT = ...; if str(REPO_ROOT) not in sys.path: sys.path.insert(0, ...)`).
- The gate regex `\bsubprocess\.(run|check_output|Popen)\s*\(` matches the LITERAL TEXT even inside a comment or
  docstring. Never write `subprocess.run (` (with a space before the paren) — it is a bare call site to the gate.

## Cause 2: `check-pr-base` — its verdict rides INSIDE the `ci-unit` job

The branch was cut from `dea3dcab`, but main advanced (by other merges) while CI ran, so
`check-pr-base` red (`HEAD NOT cut from origin/main`, merge-base != origin/main) surfaced as the `linux / unit`
step failing — the run read FAILED even though every unit test passed. Fix: rebase onto the CURRENT
`origin/main` tip, `make bot-preflight`, regenerate AGENTS/BASE into the body, re-push
(`--force-with-lease --force-if-includes`). Verify the deliverable files are byte-identical across the rebase
(sha256 per file) so earlier AC/review evidence still binds.

## The re-anchor loop

Main moved `a2ecc5b6 -> dea3dcab -> 57715198` (then further) across successive CI cycles of the same PR; each
rebase must re-run the four check-pr gates + re-verify the deliverable content before re-pushing. `ci-verdict`
reds are a snapshot-recompute (wait for run completion, don't chase); `check-pr-base` reds mean the base moved
under you (re-anchor). When the gh/actions read channel degrades (echo works, gh reads return empty), record the
honest "not confirmed this turn" state and re-read when it returns — never claim green on an empty read.
