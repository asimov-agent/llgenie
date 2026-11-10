# The subprocess policy seam (`check-proc-gate`) and aggregate trailing gates

`check-proc-gate` is the repo's ONE subprocess policy seam (issue #797). It fails when
`subprocess.run(`, `check_output(` or `Popen(` appears in `scripts/` outside `scripts/proc.py`, or on a
line that does not carry a `# proc-allow: <reason>` tag.

## Two things that make it red on a correct-looking script

1. **The tag is matched PER PHYSICAL LINE, not per call.** The gate reads the line the `subprocess.run(`
token sits on. Putting `# proc-allow: …` on the *continuation* line of a multi-line call leaves the call
line bare and it is counted as a violation:

       subprocess.run(                       # <-- violation: no tag on THIS line
           ["git", "rev-parse", ...],        # proc-allow: read branch  <-- too late, ignored
           ...)

   Fix: put the tag on the same line as `subprocess.run(`, or better:
2. **Route through the existing `_sh` seam instead of adding a new allow.** `scripts/engine_build_trigger.py`
keeps a module-level `_sh(...)` helper that already carries its `proc-allow` tag; new shell calls should go
through it rather than re-adding `subprocess.run`. An extra `# proc-allow:` is a widening of the policy
surface — prefer zero new tags.
3. **NEW code routes through `scripts/proc.py`'s named policies, period.** `proc.py` offers `run_text`,
   `run_ok`, `run_checked` (and `ProcError` with `returncode/stdout/stderr`); the `# proc-allow:` list is
   the *tracked legacy remainder* that must SHRINK to zero, so a new `scripts/check_*.py` must import `proc`
   and call a policy — never add a fresh `# proc-allow:` line. Measured on #1792: the gate read the live
   issue via a bare `subprocess.run([gh, "issue", "view", ...])` and check-proc-gate redded linux/unit
   (run 42048974998, 2/15 FAILURE) even though the pytest suite was green and the file never appeared in a
   `make ci-unit` local pass. Fix: `from scripts import proc` then
   `stdout = proc.run_checked([gh, "issue", "view", ...])` inside a `try/except proc.ProcError` that re-raises
   the same `RuntimeError(f"... ({exc.returncode}): ...")` shape — identical semantics, zero bare sites
   (verify with `grep -n subprocess scripts/check_pr_acceptance.py` → only the proc import). After the fix
   the whole job proceeded past check-proc-gate to the gate's own designed verdict.

## Verify before you claim green

    python3 scripts/check_proc_gate.py check     # rc=0, and prints 'OK: every subprocess.run/… is …'

Run it inside the pinned container with the worktree mounted (the same invocation the CI step uses), and
remember a container gate cannot run its own container — call the payload script directly.

### Guard-prove it catches the bug, with `--root` against the OLD tree

The gate takes `--root <repo>`, so you can prove red-on-old / green-on-fixed without checking anything
out — extract each tree's `scripts/` from git and point the gate at it (run in-container the same way):

    mkdir -p /tmp/pg_old/scripts /tmp/pg_new/scripts
    git archive <old-sha> scripts | tar -x -C /tmp/pg_old
    git archive <new-sha> scripts | tar -x -C /tmp/pg_new
    # RED-ON-OLD: must name the bare site and exit 1
    docker run --rm -u root -e PYTHONPATH=/repo/scripts -v /tmp/pg_old:/repo:rw -e HOME=/root \
      llgenie/test:latest python /repo/scripts/check_proc_gate.py check --root /repo
    #   -> [proc-gate] 1 bare subprocess call site(s) … scripts/check_pr_acceptance.py:156: r = subprocess.run(… , RC=1
    # GREEN-ON-FIXED: must print OK and exit 0
    docker run --rm -u root -e PYTHONPATH=/repo/scripts -v /tmp/pg_new:/repo:rw -e HOME=/root \
      llgenie/test:latest python /repo/scripts/check_proc_gate.py check --root /repo
    #   -> [proc-gate] OK: every subprocess.run/check_output/Popen … , RC=0

A green run on the fixed tree alone demonstrates nothing — the pair (names the old line, zero on the new
tree) is the proof. `check_proc_gate.py` is a CLI script (`check`/`report` + `--root`); do NOT `import`
it and call a `.check` attribute — no such symbol exists, the invocation is the program itself.

## The aggregate's trailing gates are the ones you forget

`make ci-unit` ends with a chain of `$(MAKE) check-*` targets (`check-proc-gate` among the last). A run
can report `2957 passed` for the discovered unit suite and still be RED, because a *trailing* make target
is a shape gate that reds on the new script you just wrote. **A green test module is not a green
`make ci-unit`.** Before claiming a fix green:

- read the failing job log for the actual red line and the make target / file:line it names;
- run that target's payload script in-container (e.g. `python3 scripts/check_proc_gate.py check`), not only
  the module you already had green;
- if the aggregate has other `check-*` steps after the failing one, either run them all or state plainly
  which ones you have not exercised.

Never weaken the gate or delete the tag to go green; the fix is the placement or the routing.

## Claim discipline

Do not post a "green" finish-bookend from a partial local verification. Green is a completed CI verdict at
the head you pushed (`gh api repos/<o>/<r>/actions/runs/<id> --jq .conclusion` = `success`, or the job's
`conclusion`), quoted with the run id and job id. A fix is "proven locally / CI pending" until then; say
that, and correct the record on the PR and to the planner when a claim was premature.

**A SKIPPED job is not a green verification — `skipped` is a fourth conclusion beside success/failure/
cancelled, and it means the gate NEVER EXECUTED.** When the `linux` (unit) matrix job whose `make ci-unit`
carries `check-proc-gate` reads `skipped` at the new head, the gate has not been exercised on the wire, no
matter that a container run of the payload script was green. This is the classic cascade: a guard/
scope job reds on an *earlier* step (e.g. the designed `check-pr-acceptance` self-red) and the heavy unit
row is skipped as a consequence — so there is no green wire test certifying the fix. The honest state is
"fix proven by the unit/container pair, wire CI test SKIPPED (not green), certification gated on <the
condition that un-skips it>" — never "CI green", and never a fabricated green. Read every row's own
`conclusion` (`gh api repos/<o>/<r>/actions/runs/<rid>/jobs --jq '.jobs[]|"\\(.name): \\(.conclusion)"'`),
not only the run-level `.conclusion`: a run can read `success` while the job you needed was skipped, and a
run `failure` reached the gate's designed self-red rather than a defect.
