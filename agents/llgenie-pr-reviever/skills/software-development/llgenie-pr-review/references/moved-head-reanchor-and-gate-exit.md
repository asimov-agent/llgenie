# Reviewing when the head moved, and reading gate results correctly

See also: `verdict-ref-must-name-run-or-rc-sha.md` (the write-back pin).

## 1. Dispatched head ≠ live head: re-anchor vs re-judge

The head you were dispatched on is a claim about an earlier moment. Before judging, read the live head:

```
gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha
```

If it differs from the dispatched/cited sha, classify the move by diffing the FILES the criteria grade, not the whole PR:

```
for f in <graded file> <graded file> ...; do
  git -C <repo> diff --quiet <old-sha>..<new-sha> -- "$f" || echo "DIFF $f"
done
```

- **All graded files byte-identical** (typically a rebase or base advance that brought unrelated merged work) → **re-anchor**: the change under review is the same object, so judge the criteria at the LIVE head and pin the write-back to `head=<live sha>` with a run that concluded at that head. Do not keep citing the superseded head's run.
- **Any graded file differs** → **re-judge**: re-run the graded tests/gates at the live head; the earlier evidence may describe different code.

Never write back acceptance ticks naming a run at a head that no longer exists.

## 2. Capture a target's REAL exit code — never through a pipe

`make <target> | tail -5` reports tail's status, not the target's. Record the exit code from the command itself:

```
make <target> > /tmp/out.txt 2>&1; echo "rc=$?"
```

Then decide whether a nonzero rc is a defect or by design:

- A `report`-shaped target that exits 1 **when drift/findings exist** and 0 when clean is behaving as designed. Read the script's return path (`def main`, `return 0/1`, `sys.exit`) before calling a nonzero exit a failure — a report gate that exits 0 while finding drift would be the actual bug.
- A subcommand CLI (`script.py {report,check}`) invoked with no subcommand exits 2 with an argparse usage error — invoke the documented subcommand, and read the `make` recipe to see which one the target calls.

## 3. A red job is not necessarily a separate defect

Before a verdict against a red run, read the job's step list:

```
gh api repos/<owner>/<repo>/actions/jobs/<job-id> --jq '.steps[]|{name,conclusion}'
```

The same failing step can appear in several jobs — a gate that runs early in a *scope/select* job and again as a *verdict read-back* job reds BOTH when it reds once. A red `ci-verdict`/`scope` whose failing step is the same `check-pr-acceptance` seam you are about to satisfy is the seam read back, **not** a second problem. Name the failing step, not the job. (Job logs for some runs return HTTP 404 — the step list is the reliable read.)

## 4. Gate wiring: a Makefile target is not a CI job

An AC that says a gate is "wired into the existing gate set (Makefile target + CI job)" needs both halves proven:

```
grep -nB2 -A4 '<target>' Makefile      # the recipe + .PHONY
```

Grep the CI umbrella recipe (e.g. `ci-scope` / `ci-unit`) for a `$(MAKE) <target>` line — a target that exists but is invoked by no CI-run umbrella is not wired. Then confirm the step NAME shows up in a real job's `steps[]` (section 3). A green test file proves the code, not the wiring.

## 5. Mutation-prove a "the gate fails when X" criterion

When an AC's claim is that a check FAILS on bad input, a passing run does not prove it — a check that always passes also "passes". Prove the failure path:

1. Mutate a real anchor to a nonexistent symbol/test id / invalid reference.
2. Run the check → must exit nonzero (fail closed).
3. Restore the file, run again → must exit 0.
4. Prove the restore is exact: `git -C <repo> show <sha>:<path> | diff - <restored-file>` must be empty. A restore that differs by a space silently invalidates every later test run.
