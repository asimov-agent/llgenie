# salvage-gh-guard — the gh-less container crash in the salvage audit (#2638)

Lane: `fix/salvage-gh-guard` off `origin/main`. Issue #2638 (filed from the
`feat/makefile-split-bots` lane, #2460, while that battery was temporarily unblocked by
mounting the host `gh` binary into the test container).

## What was wrong

`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/salvage-four-bucket.py`
catches only `subprocess.SubprocessError` in its `run()` seam. A missing binary raises
`FileNotFoundError`, which is an `OSError`: in the unit-test container (the test image ships
no `gh`) the argument-less invocation died at `out("gh", "pr", "list", ...)` with a raw
traceback. The no-traceback gate
(`tests/test_rebase_lane_scripts.py::test_every_python_script_is_executable_and_prints_usage_without_args`)
runs exactly that invocation over every python skill script — so the gate itself reds on any
battery whose container has no `gh`, and GitHub runners (which ship `gh`) never see it.

## What changed

- `run()` now catches `(subprocess.SubprocessError, OSError)` and returns `None`; `out()`
  degrades to `""` on a missing binary.
- `main()` checks `shutil.which("gh")`; when gh is absent it prints
  `NOTE: gh unavailable — PR identity not checked; orphan added paths are classified
  conservatively (all treated as unique)` to stderr and completes the git-only audit with
  rc=0. With no PR data, `held_by_pr` is never set, so every orphan's added paths stay
  "unique" — the conservative side of the classification.
- `tests/test_rebase_lane_scripts.py::test_salvage_audit_degrades_without_gh` is the
  regression control: a scratch bare+clone repo (real `refs/remotes/origin/main` so `main()`
  reaches the gh leg; an `orphan-unique` branch so the degraded classification leg runs),
  PATH reduced to git + python3 symlinks so no host's `gh` (mise/brew/pacman) leaks in,
  asserting rc=0, no `Traceback`, the note, and the surviving unique-orphan verdict.

## Measurements

- Container proof (no `gh` mount): `NO_GH_IN_CONTAINER` confirmed;
  `python -m pytest tests/test_rebase_lane_scripts.py -q` rc=0 — 27 passed (the 26
  pre-existing tests plus the new control) in the gh-less test container.
- Direct AC1 replay in the same gh-less container: `python
  agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/salvage-four-bucket.py`
  printed the full four-bucket audit, `DIRECT_RC=0`, zero `Traceback` lines on stderr, and
  the degraded note.
- The degraded audit still prints the four buckets, still preserves the unique orphan, and
  deletes nothing (unchanged read-only contract).

## Current status

OpenSpec `salvage-gh-guard` validated; tasks ticked against measured rc=0 proofs; PR CI
tracked in the PR body. This closes only #2638; #2460/#2461 keep their own PRs.
