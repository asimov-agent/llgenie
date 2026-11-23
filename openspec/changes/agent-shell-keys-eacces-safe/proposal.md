# Fix: the agent-shell-keys check aborts on an unreadable Hermes candidate instead of skipping it

<!-- Part of Issue: [#3020](https://github.com/asimov-agent/llgenie/issues/3020) -->

## Why

`make agent-shell-keys-check` is the preflight every agent bot leg runs before it hands a credential
to the agent container. On the published `agent:latest` image it now dies with
`[agent-shell-keys] FATAL: [Errno 13] Permission denied: '/root/.hermes/hermes-agent/tools/environments/local.py'`
(issue #3020: run `45146906862`, job `implement`, job id `137598403140`; reproduced on this host at
head `cd1c357bb`, `make agent-shell-keys-check` → `mk/agents.mk:57: _agent-shell-keys-check] Error 2`).

The cause is one call. The container runs as uid 999 `agent` and `/root` is mode `0700 root`, so the
hardcoded `/root/.hermes/hermes-agent` candidate can never be read — but `hermes_root()` tests that
candidate with `Path.is_file()`, and `is_file()` re-RAISES `PermissionError` (it swallows only
ENOENT/ENOTDIR/EBADF/ELOOP). One unreadable candidate therefore ends the whole check before the real,
agent-owned install at `/home/agent/.hermes/hermes-agent` — the one the agent's own runtime uses
(`[jev-preflight] … written to /home/agent/.hermes/.env`) — is ever consulted. Every agent bot leg
that starts with a credential (issue-bot, issue-dedupe, search-smoke, issue-refiner) reddens its
preflight step, and no issue/PR can be produced by those lanes.

## What Changes

- `scripts/agent_shell_keys_check.py`: candidate roots are tested through a readable-only probe —
  a candidate whose probe raises `PermissionError` is SKIPPED, not fatal — so discovery falls through
  to the Hermes install the container user can actually read.
- The decision is printed, never silent: the chosen root and the candidates skipped as unreadable
  (repo rule: decision notes are printed).
- `tests/test_agent_shell_keys.py`: a negative-control test that FAILS on the pre-fix tree (an
  unreadable candidate must not abort discovery), the fall-through to the readable install, and the
  unchanged loud failure when no candidate is readable.
- Unchanged: the credential list, the `_HERMES_FORCE_` twin seam, the Hermes terminal probe itself,
  the fail-closed exit codes, and the rule that no credential value is ever read or printed.

## Impact

- Affected specs: `agent-shell-credentials` (MODIFIED — Hermes install-root discovery).
- Affected code: `scripts/agent_shell_keys_check.py`, `tests/test_agent_shell_keys.py`.
- No workflow, image, or Makefile surface changes; no live engine image build; no secret value is
  read, printed, or stored.
