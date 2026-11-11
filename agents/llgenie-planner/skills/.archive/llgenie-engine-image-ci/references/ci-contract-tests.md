# The contract suites that red when you touch a workflow, a bot prompt or a target

llgenie type-checks its CI. A workflow or bot edit that is functionally correct still reds `linux / unit`
(or `macos / unit`) on tests that name the SYMPTOM, not the cause. Run the relevant suites in the test
image before pushing:

```bash
docker run --rm -v "$PWD":/repo:rw -w /repo llgenie/test:latest \
  python -m pytest tests/test_workflow_guards.py tests/test_dispatch_forms.py \
    tests/test_bot_pipeline_isolation.py tests/test_agents_unattended.py \
    tests/test_agent_shell_keys.py tests/test_bot_time_budget.py -q
```

## Adding a trigger to a workflow

- **`workflow_dispatch` is a contract, not a flag.** `tests/test_workflow_guards.py` requires every
dispatchable workflow to carry the byte-identical owner/collaborator `guard` job (checks `github.actor` AND
`github.triggering_actor`, accepts only `admin|maintain|write`, runs before any secret is read), and
`tests/test_dispatch_forms.py` requires its header to state what the run does plus `Trigger surface:`,
`Flow:` and `Never:` lines. A workflow that never had a dispatch trigger has none of that, so adding
`workflow_dispatch:` to make something hand-runnable reds ~7 tests while the feature is correct. Prefer a
make target or a `gh run rerun` as the manual path; if dispatch is genuinely needed, copy the guard job
verbatim from a guarded workflow and copy the header shape from one too.
- **A `schedule:` block is not a guarantee it fires.** A cron on a workflow that also has `workflow_run`
can produce zero runs while the API reports the workflow `active` and another workflow's cron in the same
repo runs fine. Verify with the runs API (`.../actions/workflows/<id>/runs?per_page=30` grouped by
`.event`) before relying on a sweep, and wire anything time-sensitive to an event that demonstrably fires.

## Cron minutes are a global namespace

`tests/test_bot_pipeline_isolation.py` allows one workflow per minute: the *minute* must be unique across
all workflows, and the every-hour bots additionally reserve their minutes (`0, 7, 17, 30, 37, 43`). A
`37 */6 * * *` collides with `queued-alarm.yml`'s `7,37 * * * *` on every day of the week. Pick a free
minute by listing them first:

```bash
grep -h 'cron:' .github/workflows/*.yml | sed 's/.*cron: *"//' | cut -d' ' -f1 | sort -u
```

## Agent-leg prompts

- **Every `hermes -z` prompt carries the UNATTENDED rule** (`tests/test_agents_unattended.py`). The test
derives the expected count from the Makefile, so a NEW prompt (including the rebase-bot's `$$(cat)` stdin
prompt) fails until the rule text is appended: never ask, never wait, take the path that needs no decision.
A detached run that asks a `clarify` question prints `Input required; detached without cancelling` and exits
**3** — the leg reads as "changed nothing" unless the workflow names rc=3 separately.
- **A leg may forward only credentials.** `tests/test_agent_shell_keys.py` requires every `-e NAME` to be in
`AGENT_SHELL_KEYS`; a path or flag (`FIX_REPORT_FILE`) is not a credential, so set it INSIDE the container
instead of forwarding it: `bash -lc 'FIX_REPORT_FILE="$(REPORT_FILE)" scripts/x.sh'` with the make variable
expanded by make before the shell.
- **The wall clock must fit the work.** `tests/test_bot_time_budget.py` asserts
`rounds * (check_minutes + agent_minutes) <= job.timeout-minutes`; raising a retry count without raising
`timeout-minutes` means the job is cancelled mid-repair and the feature never completes its rounds.

## Secrets and docs

- A new credential name goes in three places or `make test-unit` reds: the workflow's `secrets.<NAME>`
transfer, the Makefile's `AGENT_SHELL_KEYS`, and `scripts/check_secret_output.py::SECRET_VARS`.
- `make check-docs` fails when a `##`-help make target is absent from `README.md`, and when an
`agent-wiki/` entry references no issue or PR. `make check-wiring` fails on a script or test with no target,
or a target missing from `.PHONY`.
- Regenerate the README dispatch table after any dispatchable-workflow change:
`docker run --rm -v "$PWD":/repo:rw -w /repo llgenie/test:latest python scripts/check_dispatch_forms.py report`
(the `make` wrapper runs `check`, so it cannot print the table for you). A header that names a clock time
must match a literal cron field — `*/6` can never satisfy a "18:37 UTC" claim, so describe the cadence in
words instead.

## Worktree hygiene

One worktree per change off `origin/main`; a draft written into an already-pushed worktree must be copied
out (`cp` to the scratch dir) and `rm`'d before the commit, or it lands on the wrong PR.
