# 2026-10-23 — the fix-bot is woken by the failure it repairs (#538)

**Issue:** [#538](https://github.com/asimov-agent/llgenie/issues/538) · **PR:** the PR that closes it

## What was wrong

The fix-bot could not repair the PRs that needed it:

- **No failure trigger.** Only `schedule: 17 * * * *`, and GitHub delivered ~9 runs in 36h (01:28Z, 22:17Z,
  18:30Z, 13:45Z, 07:31Z …). A PR that went red between sweeps waited hours; the failed `CI` run was a
  `workflow_run` nobody consumed.
- **Three attempts, never unverified.** `fix_loop.sh` ran `make ci-unit` locally and exited 1 when it was still
  red, so nothing was pushed. A failure the runner cannot reproduce — `macos / unit` red on PR #533 at 04:36Z
  (`tests/test_engine_skills.py::test_digest_reads_the_live_registry_and_retries_a_failed_lookup`) while
  `linux / unit` was green — was therefore never attempted.
- **Always `make ci-unit`**, whatever job actually failed.

## What changed

- `fix-bot.yml`: `workflow_run: workflows: ["CI"], types: [completed]`, acting only on a `pull_request` run
  with `conclusion == 'failure'`; resolves the PR with `make auto-merge-resolve`; captures
  `gh run view <id> --log-failed`; dispatches that PR with `ATTEMPTS=5` and `REPORT_FILE`; new `report_file`
  dispatch input.
- `scripts/fix_bot_sweep.py`: `--pr N` evaluates that PR only; `--report-file` is passed through;
  `--max-attempts` defaults to 5.
- `scripts/fix_loop.sh`: `ROUNDS` defaults to 5; `FIX_REPORT_FILE` repairs from the run's log and reports
  `UNVERIFIED` (CI re-runs and re-triggers), instead of discarding the attempt.
- `Makefile`: `ROUNDS` default 5, `REPORT_FILE` plumbed into the container env and the loop.

## Verified

- `pytest tests/test_fix_bot_sweep.py tests/test_fix_loop.py` in `llgenie/test:latest` → 35 passed.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=fix-bot-retrigger`, `make openspec-tasks-check` → green (the workflow gate
  validates the new `${{ }}` and YAML).
- `make test-unit` → in the PR checks.

## Why PR #533 was red and unrepaired

`macos / unit` failed on a live-GHCR digest lookup — a flake in an unrelated test, not the change; `linux /
unit` was green. The fix-bot's check is `make ci-unit` (Linux), so it could not reproduce it; and the sweep had
not run since 01:28Z. With this change that failure wakes the bot within minutes, hands it the macOS job log,
and allows up to 5 attempts, each verified by CI.

## The red the fix-bot left behind (run 39921364286)

Both unit jobs went red on the branch: `tests/test_agent_nerve.py::test_the_key_reaches_the_container_through_make_targets`
asserted the CONTIGUOUS string `scripts/agent_jev_preflight.sh && scripts/fix_loop.sh`. Passing
`FIX_REPORT_FILE="$(REPORT_FILE)"` into the loop put a word between them, so the assertion failed
(`1 failed, 5034 passed` on linux, the same on macos) while the preflight still ran first — the behaviour
was right and the test pinned the spelling. The assertion now reads the invariant it means: both commands
are in the `fix-loop-image` recipe and the preflight's position is before the loop's.
