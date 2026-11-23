# 2026-11-23 — agent-shell-keys check: an unreadable Hermes candidate is skipped, not fatal (issue #3020)

## What was verified against the issue

- The CI failure was reproduced on this host against the PUBLISHED image: `make agent-shell-keys-check`
  died with `FATAL: [Errno 13] Permission denied:
  '/root/.hermes/hermes-agent/tools/environments/local.py'` (`/tmp/shellkeys-repro.log`, head
  `cd1c357bb`) — the same shape as run `45146906862`, job `implement`, job id `137598403140`.
- Cause measured in the image, not guessed: `docker run --rm ghcr.io/asimov-agent/llgenie/agent:latest`
  reports `uid 999 agent`, `/root` as `drwx------ root`, and the agent's own Hermes install readable at
  `/home/agent/.hermes/hermes-agent/tools/environments/local.py` (+ its `installs/*/*/venv/bin/python`).
  `hermes_root()` probed the hardcoded `/root/...` candidate with `Path.is_file()`, and `is_file()`
  RE-RAISES `PermissionError` on the interpreter the image ships (it swallows only
  ENOENT/ENOTDIR/EBADF/ELOOP) — one unreadable candidate ended the preflight before the readable
  install was consulted.
- Fix: candidate roots go through `_hermes_candidate()`, which turns an unreadable candidate into an
  absent one (`PermissionError` → skip). The chosen root and every skipped candidate are printed —
  `[agent-shell-keys] hermes root: … (skipped: … unreadable (…))` — because the root the probe ran
  against is part of the verdict (decision notes are printed, never silent). The no-readable-root case
  stays loud: the reason now names which candidates were unreadable.
- Tests (`tests/test_agent_shell_keys.py`, 4 new, hermetic): the unreadable candidate is planted as a
  `PermissionError` raise (via a `Path` stand-in) rather than as a directory mode, because
  `Path.is_file()` swallows EACCES on Python 3.14 and re-raises it on the image's interpreter — the
  shape that actually broke must be the shape proven. Negative control measured: the 4 new tests FAIL
  on the pre-fix tree (4 failed / 10 passed with the fix stashed) and pass after (14 passed).

## Live proof

`make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS="NOUS_API_KEY GH_TOKEN TYPESAFE_API_KEY"` — the
failing job's own key set — is GREEN on this host in the published `agent:latest`
(`OK: 3 credential(s) visible in the agent's shell`, rc=0, `/tmp/shellkeys-green3.log`), with the
`/root` candidate reported as skipped instead of ending the run.

## Status

Issue #3020 stays open until its PR (#3027) merges; the bot legs that were blocked by this preflight
(issue-bot, issue-dedupe, search-smoke, issue-refiner) get their credential proof back at that merge.
