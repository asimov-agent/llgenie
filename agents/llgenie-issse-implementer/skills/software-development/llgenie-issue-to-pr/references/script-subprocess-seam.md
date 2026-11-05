# check-proc-gate: Python scripts must call subprocess through `scripts/proc.py`

## The rule
In `asimov-agent/llgenie`, a script under `scripts/` that shells out must route the
call through the repo's single subprocess seam, `scripts/proc.py` — never call
`subprocess.run` / `subprocess.check_output` / `os.system` directly. The lint gate
`make check-proc-gate` (the repo's "one subprocess seam", issue #797) runs inside the
`linux / unit` matrix and reds the whole unit job on a direct call, **after** the
tests themselves pass — so the unit row fails with `check-proc-gate … Error 2` even
though every `pytest` assertion was green.

## Why it bites late
`make test-unit` locally can be fully green (all tests pass) while CI's unit job is
RED, because the local target and CI both run the gate but you only *read* the
pytest summary. The failure is in the gate step of the job, not the tests. When the
unit row is red but your local suite passed, read the job log for the step name —
`check-proc-gate` is the evidence, not a flaky test.

## The two call shapes
- `proc.run_ok(argv, …)` — non-raising; returns a result whose `returncode` you
  inspect yourself. Use when you need to branch on the rc (e.g. a write that may
  legitimately fail and you fall back).
- `proc.run_checked(argv, …)` — raises on a non-zero rc. Use when a failed call is a
  hard error (e.g. fetching an issue body you cannot proceed without).

Map each existing `subprocess.run(...)` by intent: inspect-rc → `run_ok`;
raise-on-failure → `run_checked`. Do not "fix" the gate by adding a
`# proc-allow` suppression comment if a real migration fits — migrate.

## Where it surfaces in the gate vocabulary
Symptom: `linux / unit` = fail, `ci-verdict` = fail, everything else green; the job
log shows `check-proc-gate` at a `Makefile:` line and `ci-unit … Error 2`. The fix is
in your new script, not in the CI config.
