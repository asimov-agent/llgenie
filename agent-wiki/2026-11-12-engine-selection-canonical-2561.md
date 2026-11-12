# Engine selection canonical — a scoped build dispatch must name its cell or die (#2561)

Issue: #2561 · PR: #2562 · branch: feat/engine-selection-canonical

## What was verified

- **The measured defect.** The registry-liveness self-remediation wave for squash `aa700cf27`
  dispatched 28 scoped `engine-build push=true` runs; nine completed `completed success` having
  built and published nothing — runs 43149732453, 43149735782, 43149739069, 43149741957,
  43149744886, 43149748002, 43149751256, 43149753954, 43149757005, each with a build job named
  `engine-build-none-none`. The liveness dispatch derived engine ids by parsing ghcr **package
  URLs**, and package names legally replace dots with dashes (`engine_image.py`:
  `params['id'].replace('.', '-')`): `llama.cpp` arrived as `engine=llama-cpp`, `matrix` matched
  no params id, synthesized its `{"engine":"none","arch":"none"}` placeholder and exited 0, and
  every `if: matrix.engine != 'none'` step skipped — a vacuous nine-run success while the nine
  dotted cells stayed unpublished.
- **The permanent fix (three code changes, one contract).**
  1. `scripts/check_engine_pins_published.py` now prints a machine-readable contract line per
     unpublished cell: `[select] <engine-id> <variant> <tag-suffix>` — the COMMITTED params id,
     dots intact.
  2. `.github/workflows/registry-liveness.yml`'s dispatch step reads ONLY those `[select]`
     lines; the package-URL reverse-parse (`cut -d: -f1`) is gone from the dispatch path.
  3. `scripts/engine_image.py::matrix()` hard-fails an explicit `--engine`/`--arch` that
     resolves to zero committed cells — `no committed engine id 'llama-cpp'` /
     `'llama.cpp' … no committed cell … committed variants` — CLI and Makefile exit non-zero.
     The placeholder row survives ONLY for unscoped sweeps (`--changed` nothing-moved,
     whole-fleet), which GitHub needs to keep a matrix legal (run 38105450418).
  4. `Makefile` `build-engines` gained `|| exit 1` on the matrix assignment, so a failing
     matrix reds the target instead of flowing an empty row list into `xargs -r` (rc 0).
- **Gate proofs (this tree).** `make check-engine-pins-published ALL=1` printed 24 `[select]`
  lines including all nine dotted cells (`[select] llama.cpp vulkan 7d7f0287-221a5e64-vulkan`
  …). `make engine-build-matrix ENGINE=llama-cpp` exited non-zero naming `llama-cpp`;
  `make engine-build-matrix ENGINE=llama.cpp ARCH=cpu` exited 0 with exactly the one
  `llama.cpp`/`cpu` row. Targeted pytest: 9/9 new+updated tests green; the two touched test
  files 47/48 (the lone failure is the live `check_committed` registry gap from `aa700cf27`
  itself — tracked by #2529 and its dispatch sweep, not by this change); the six consumer
  test files 250/250. `make openspec-validate`, `make check-workflows`, `make check-wiring` rc=0.
- **Fleet state at time of writing.** Four of 28 committed tags were published
  (`freetoken:cuda/rocm`, `litert:cpu`, `mlx:cuda`); the nine dotted cells were re-dispatched
  out-of-band with canonical ids (`gh workflow run engine-build.yml -f engine=llama.cpp …`),
  and full-fleet drain is verified under #2529, not here.

## Decisions

- The selection contract lives in the GATE's own output, not in a downstream parse of a registry
  URL: ghcr is a namespace where the canonical id is illegal, so any URL-to-id reverse-parse is
  a bug factory by construction.
- `none/none` stays a legal placeholder for UNscoped no-op sweeps (empty matrix include lists
  fail at GitHub load time); it became legal ONLY when selection is implicit.

## Current status

Implementation on `feat/engine-selection-canonical` (openspec change `engine-selection-canonical`,
all implementation tasks ticked); ships through the PR named in `docs/changes.d`. The dispatch
wave's completion (fleet fully published, main green) is tracked by #2529/#2559.
