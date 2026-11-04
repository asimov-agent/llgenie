# Verifying a fix and watching CI

## Network-marked tests run for ~16 minutes — never from a short foreground window
The registry `sync` live tests hit the network and take ~16 min. A foreground run (or any wrapper with
its own 300–420 s cap) is killed mid-sync, which reads as a failure. Run them as **durable background
jobs with `notify`**, and stand on the real conclusion — do not report a t/s / pass from an in-flight run.

## An empty output with exit code 2 is a capture artifact, not a test failure
A pytest invocation that returns RC=2 with **zero bytes** on stdout *and* stderr while a trivial pytest
and a plain `import` of the same module both succeed is not a broken test — it is the output channel
swallowing or the caller killing it before it writes. Do not conclude the test is defective. Prove
execution by either:
- running `pytest.main([...])` **in-process** in a wrapper that swaps `sys.stdout`/`sys.stderr` into an
  `io.StringIO`, writes the captured buffer + `pytest.main`'s returncode to a JSON file, then reads that
  file back; or
- passing real file descriptors to `subprocess.run(stdout=open(...,'w'), stderr=open(...,'w'))` so the
  child writes straight to disk, bypassing the capture path.
If the in-process run *times out while still running*, that proves the test executes — it is slow, not
broken. The authoritative green is the real CI job conclusion, not a local reproduction.

## Map a test class to the workflow that actually runs it BEFORE claiming a PR-head verdict
A PR-head CI run and the pipeline that proves a network/acceptance test are DIFFERENT workflows. Read the
`on:` blocks and the make target before concluding "the acceptance case passed at this head":
- **`linux / unit` (ci.yml) runs `make ci-unit` = hermetic only** — its target is
  "unit tests + registry / skill / Strata / engine-param / quant-catalog checks". It does **NOT** run
  `test-unit-network`; `ci.yml` contains zero `network` references. A green `linux / unit` at a PR head
  says nothing about a `@pytest.mark.network` case.
- **The `@pytest.mark.network` set runs only in `ci-hf-live.yml`**, whose own header states it is the
  "merge-to-main real-Hub test pipeline" and "never runs in a pull request". So a **PR head can never
  carry a ci-hf-live verdict** — that run is created only when the change lands on `main`.
Consequence: when asked to post "the concluding ci-hf-live result at the PR head", first prove whether
such a run can exist. If `actions/runs?head_sha=<pr-head>` shows only `CI` / `ci-scope` / `holds` and no
`ci-hf-live`, the requested verdict does not exist by design — report the completed PR CI run id
(all jobs green) as the head verdict, plus a LOCAL deterministic re-run of the same
rank/serving code as behaviour evidence, and state plainly that the network acceptance re-runs on `main`
only. Do not rubber-stamp a premise (e.g. "linux/unit runs the acceptance case") that the workflow
definition contradicts — verify the target split first, then report accurately.

## Match GitHub Actions job names by substring, never equality
The matrix job is named `linux / unit`, not `unit`. A `jq 'select(.name=="unit")'` (or a watcher built
on it) returns `[]` forever and silently runs to timeout. Query/watchers must use
`select(.name|contains("unit"))` (or the full literal name). Before trusting an empty job list, print
the raw `.jobs[].name` set once to confirm the exact shape.

## Stage change-note files by explicit path — never `git add -A`
When satisfying the `check-docs` gate (an `agent-wiki/<stem>.md` note, a `docs/changes.d/<stem>.md`
fragment, and the re-rendered `CHANGES.md`), `git add -A` scoops untracked scratch/diag files into the
docs commit. Stage each path explicitly and re-check `git show --stat` before pushing.

## A CHANGES.md conflict is two legitimate rows — keep both
A concurrent merged PR adds its own `changes.d` row and collides in the rendered `CHANGES.md`. Resolve
by keeping both rows (not deleting either), then re-run `make changes-index` and re-verify `check-docs`
before the force-push.
