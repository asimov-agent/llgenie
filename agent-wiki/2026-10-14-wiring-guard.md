# 2026-10-14 — the wiring guard (issue #237)

## What was verified against the spec

- `scripts/check_wiring.py` builds the wiring graph from the real files: make targets plus
  their **prerequisites** (an edge: `ci-lint: bash-check` runs `bash-check`), both
  makefiles (`Makefile`, `tools/Makefile` — `make -C tools x` is followed to its target),
  workflow steps, and per-document dependencies (python imports; a path a document runs or
  reads; a path named only to assert its **absence** wires nothing).
- Two questions, both from the files: is a document wired to *any* target, and is it
  reached by the targets the workflows actually call.
- `checks` errors: a document wired to nothing; a document only a non-CI target reaches
  with no recorded decision; a stale decision (CI reaches it now, or the file is gone); a
  malformed decision; a workflow calling a make target that does not exist.
- Measured on `main`: 84 documents (50 tests, 34 scripts), 80 run in CI, 4 host-only, 125
  make targets, of which CI calls 35 — and exactly two documents unusable: the new
  `check_wiring.py` itself (wired by `make check-wiring`) and
  `tests/test_engine_bump_build.py` (deleted).

## The live defect

`tests/test_engine_bump_build.py` was named by **no** target, chain or workflow step. Its
own docstring said it is out of `test-unit` (no docker socket there) and pointed at
`make test-engine` as "the CI path" — but nothing ever ran the file, so it read as coverage
while proving nothing. The real llama.cpp cpu image build it asserts is the
`engine-image-llama.cpp-cpu` matrix job (every push run), so the file is deleted and the
stale `ci.yml` comment ("serve: pytest tests/test_engine_runs.py") now points at
`scripts/engine_smoke.py --image`, which is what actually runs that file.

## Host-only decisions (the "decision, not accident" part)

`tests/fixtures/host-only-wiring.json` records the four documents a CI runner cannot run:
`tests/test_health.py` (the installed launcher serves on this host's real backend — CI's
cpu-health stage answers "hi" through the engine image instead), and the three native-Metal
files (`test_native_engine_real`, `test_native_engine_light`,
`test_interactive_tensorfold_real`). Each carries `reason`, `target`, `decided` — and the
gate fails the moment CI would reach one, so the record cannot rot. Same shape as
`data/unsupported-engines.json` in #234.

## The other half (filed, not folded in)

The same audit found a dead **target**, which a document-level guard cannot see:
`make test-install-ci` is called by no CI job (its docstring claims the pipelines run it),
and it is the only caller of `test-install-host` / `test-health-host` /
`test-install-trend` — so those never run in CI either. Filed as #239 (option 1: wire it
into `ci-install`; option 2: retire it and say what now covers its path). The Nerve/JEV
setup for the containerized issue-implementer is #238.

## Can this guard be fooled?

- A test that mentions another file's path is wiring *only* when the mention is a run/read
  (`REPO / "scripts" / "x.py"` in an argv, `read_text()`), not an absence assertion. A
  mention inside `assert ... not in` is ignored *on purpose* — that is exactly how a dead
  file looked wired.
- A document imported by a wired module counts as wired (that is a real dependency).
- A `def` inside a script is not examined; this guard is about documents and targets,
  which is where the repo's rule was being broken.

## Status

OpenSpec change `wiring-guard`, branch `feat/wiring-guard`, PR against
`asimov-agent/llgenie` (issue #237).
