# Change: salvage-gh-guard (issue #2638)

## Why

`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/salvage-four-bucket.py`
calls `gh` through `subprocess.run` and catches only `subprocess.SubprocessError`. A missing
binary raises `FileNotFoundError` (an `OSError`), so in the gh-less unit-test container
(`ghcr.io/asimov-agent/llgenie/test` ships no `gh`) the branch-classification leg dies with a
raw traceback. The gate that enforces "no skill script tracebacks"
(`tests/test_rebase_lane_scripts.py::test_every_python_script_is_executable_and_prints_usage_without_args`)
is exactly what crashes: loud on gh-less local batteries, invisible to GitHub runners (which
ship `gh`). Filed from the `feat/makefile-split-bots` lane (issue #2460) while that lane's
battery was temporarily unblocked by mounting the host `gh` into the container.

## What Changes

- `run()` catches `OSError` next to `subprocess.SubprocessError` and returns `None`, so every
  `out()` of a missing binary degrades to an empty result instead of raising.
- `main()` detects a missing `gh` (via `shutil.which`) and prints a degraded-note line naming
  the consequence — PR identity not checked, orphan tips classified conservatively (every added
  path treated as unique) — then completes the git-only audit with rc=0.
- A regression test drives the script with `gh` absent from `PATH` and asserts rc=0, no
  `Traceback`, and the degraded note.

## Impact

- Spec: `specs/salvage-audit-degradation/spec.md` (new capability, delta-only).
- Code: the one skill script; `tests/test_rebase_lane_scripts.py` gains one test.
- Docs: `agent-wiki/` entry, `docs/changes.d/` fragment, `CHANGES.md` row.
- Gates: the existing no-traceback test goes from crash-by-environment to a passing proof;
  local unit batteries stop needing the `gh` mount workaround.
- This change closes ONLY issue #2638.
