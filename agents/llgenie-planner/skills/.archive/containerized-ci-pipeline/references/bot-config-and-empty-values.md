# Bot configuration: empty values, forwarding, and proving the fix

How a scheduled bot's SETTINGS break it, and how to make the fix provable.
Companion to `references/adding-a-pipeline-to-this-repo.md` (registrations and the
write path).

## An empty value is a MISSING value — for settings, not only credentials

`int(os.environ.get("CAP", "2"))` treats UNSET as the default but a SET-BUT-EMPTY
value as a value, and `int("")` raises. A wrapper that forwards
`CAP="$(CAP)"` unconditionally manufactures exactly that empty value for every call
that does not set it, so the failure lands in whichever step happens to use the
default — often the step whose job is to raise an alarm, which then goes silent
while the run is red for a reason nobody reads.

Rules:

- ONE reader for numeric settings: unset **or** blank (`""`, `"   "`) returns the
documented default; a non-numeric value raises an error NAMING the variable and
what it held (a typo must never be silently read as the default). Provide the int
and float forms in the same module.
- Convert EVERY bare `int(os.environ…)` / `float(os.environ…)` in the tree in the
same change, and add a repo-wide guard that fails on a new one — one un-converted
site is the same bug waiting for the next wrapper.
- A make wrapper forwards a setting only when it is set:
`$(if $(CAP),CAP="$(CAP)",)` — never `CAP="$(CAP)"` on its own.
- One place per setting. A workflow step `env:` that the same step's command line
overrides is dead configuration: a reader (and the agent fixing the crash) sees it
"configured" in the place that does nothing. Put it in `env:` XOR on the command line.

## Prove the guard bites: revert the SOURCE, not the test

A regression test that passes on the old code locks nothing, and the repo rulebook
will say so. The cheap mechanical proof, without a second checkout:

1. finish the change and the tests, run them green;
2. `git stash push -- <the source paths>` — path-limited, so the new/modified TEST
   file stays in the tree and an untracked new module stays too;
3. run the new tests and confirm they FAIL, for the reason you expect (read the
   detail, not just the count);
4. `git stash pop` and re-run green.

Quote both halves (the red run's lines and the green count) in the PR body. If a
new check still passes on the old source, it asserts something the old code already
did — tighten it or drop it.

## Diagnosing "the scheduled bot is red"

Order that works, and why each step is not skippable:

1. `gh run view <run-id> --json jobs` → which JOB failed (not the whole run).
2. `gh run view <run-id> --log` and read only the failing step's lines: the last
   traceback names the line and the value. Do not theorise before this.
3. Reproduce the EXACT command locally — the `make` invocation the step runs, with
a stub CLI on `PATH` for the network (`gh`) and the setting UNSET in the
environment. If that passes locally, the difference is the CI environment; if it
fails, you have the bug.
4. Fix at the shared reader/wrapper, then run the module, then the whole suite.
5. After the merge, DISPATCH the workflow on the default branch and confirm every
job's conclusion — a green PR proves the change compiles under CI, not that the
cron path now works.
