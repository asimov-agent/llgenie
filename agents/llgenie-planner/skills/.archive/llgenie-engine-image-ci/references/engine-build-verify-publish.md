# Building, verifying and publishing engine images

Depth for the rules in SKILL.md. Everything here is llgenie-specific and skippable when you are
only editing docs.

## The one pipeline

```
params (per engine x variant)  ->  Dockerfile  ->  build-engine  ->  verify the binary  ->  push-engine
containers/engines/params/*.json   dockerfiles/<id>/Dockerfile.<arch>            (inside the image)   (hash + :arch + :latest)
```

The params are the single source. A cell = one engine x one variant. The committed params hold both
`prebuilt: true` (start FROM someone else's image / pip a wheel) and `prebuilt: false` (compile
here), and that flag is a promise the rest of the pipeline relies on.

Useful scopes (all one code path, `scripts/engine_image.py`):

```bash
make build-engine ENGINE=<id> ARCH=<cpu|cuda|rocm|vulkan>        # one cell
make build-engines ENGINE=<id>                                   # one engine, every arch it supports
make build-engines ARCH=<cuda>                                   # one arch, every engine
make build-engines                                               # every cell, in parallel (JOBS=)
make build-engines FORCE=1 VERIFY=1                              # every cell rebuilt from scratch, then verified
make test-engine-image ENGINE=<id> ARCH=<arch>                   # the binary flag probe
make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect  # what CI and the sweep call
make push-engine ENGINE=<id> ARCH=<arch>                         # publish after the probe
make engine-build-matrix [ENGINE=] [ARCH=]                       # the JSON the dispatch matrix reads
make engine-source-report                                        # source vs prebuilt census + tracked exceptions
make check-engine-source                                         # CI: a claimed source build must compile
```

## Guarding the "built from source" claim

A cell lies in exactly three ways, and each is statically checkable against the committed params
(no Docker needed):

| lie | check | signal |
|---|---|---|
| pip-installs a published wheel / downloads a release tarball | does any install step compile? | build regex: `cmake`, `make`, `ninja`, `cargo build`, `go build`, `setup.py`, `-m build`, `get_llama_cpp(`, `CMAKE_ARGS=`, or a pip install of the tree (`--no-build-isolation`, `-e .`, bare `.`) |
| clones a moving branch | is the clone pinned? | pin regex: 7-40 hex, `--branch`, `-b <ver>`, `git checkout <ref>`, `tag v<digits>` |
| starts FROM its own upstream image | first `FROM` of the generated Dockerfile | reject when the image repo names the engine and is not `llgenie/base-*` |

Pitfalls that cost a run each:

- **`pip install .` is not `pip install <pkg>==<ver>`.** Match the tree install (bare `.`, `-e .`,
  `--no-build-isolation`), never the substring `pip install`.
- **Strip backend words from the engine id before matching the base repo.** `exllamav3-rocm` builds
  FROM `rocm/pytorch` — a toolchain base, not that engine's image. Tokenise the engine id, drop
  `rocm|cuda|vulkan|cpu|metal|gpu` and short tokens, and only then look for the name in the repo.
- **Plain `grep` for a python-driven native build.** Strata compiles llama.cpp through
  `get_llama_cpp()` inside a `python -c`, so `cmake` appears nowhere in its install text.
- **Tracked exceptions, not silent passes.** Cells that genuinely have no source build yet carry an
  entry with the reason and its issue; the gate reports them and fails only on an untracked cell.
  Removing the entry is what "converted" means.

## FORCE must bypass the layer cache

```bash
make build-engine ENGINE=<id> ARCH=<arch> FORCE=1
make build-engines FORCE=1 VERIFY=1
```

- Skipping the `_available(tag)` short-circuit is only half of it: buildx still reads
  `--cache-from type=registry,ref=<registry>/<name>:buildcache-<variant>`, so a fully cached
  "forced" build re-tags the previous layers and compiles nothing. Force must add `--no-cache`
  **and** drop `--cache-from` (keep `--cache-to`, so the next run still benefits).
- `build()` must pass `force` to `build_base()` — otherwise the shared toolchain base is reused and
  the forced engine build sits on stale layers.
- A parallel sweep only forwards what its xargs row carries: add `FORCE` next to `PUSH` and `VERIFY`
  in the `build-engine` invocation, or the flag silently applies to nothing.
- What a real forced run looks like (no `--cache-from`, hundreds of compiler lines):

```
[engine-image] $ docker buildx build --builder default --no-cache -t llgenie/base-cpu:<tag> --load …
[engine-image] $ docker buildx build --builder default --no-cache -t llgenie/llama-cpp:<sha>-<hash>-cpu --load …
[engine-image] built llgenie/llama-cpp:<sha>-<hash>-cpu
```

- A parameter-only change (a `detect` line, a flag) changes the baked `params.json` and therefore the
  image tag hash. Rebuild that cell and re-verify before claiming the fix works — the unit test does
  not prove the image.

## Verifying the binary

- Probe the *documented* flags plus both families, inside the built image, at the documented binary
  path (`--version`/`-V`, `--help`/`-h`). A serving (cpu) cell must ALSO answer on the OpenAI API,
  and the flag probe runs **before** the serve test, joined with `&&` so a bad binary stops the row.
- An argparse CLI with no version flag is not a failure: give it a `help` probe policy (help family
  required, version taken from the image's own `detect`) instead of demanding `--version`.
  Adding a policy is a three-file change — the runner's verdict function, the skill validator's
  allowed policy set, and the manifest test that asserts those values. Miss the validator and
  `skills-validate` rejects every skill that uses the new policy.
- `set -o pipefail` + `grep -q` = SIGPIPE. `grep -q` exits at the first match, the engine writing into
  the pipe dies of SIGPIPE, and the step reports 141 — a healthy binary reported as missing. Use
  `grep … > /dev/null` (reads to EOF). Grep every `skills/engines/*/SKILL.md` for `grep -q` after a
  detect failure that names exit 141.
- A `test-engine-image`-only test file fails loudly when run bare (`LLGENIE_TEST_ENGINE` unset). That
  is the harness talking, not a regression: run it through `make test-engine-image`.

## Publishing names

One built image is published under three refs, in this order:

1. `…/<engine>:<sha8>-<hash>-<variant>` — immutable hash tag
2. `…/<engine>:<variant>` — moving per-arch tag
3. `…/<engine>:latest` — claimed by exactly ONE variant per engine (cpu when it has one, else the
   only/first variant), because matrix rows run in parallel and would otherwise race the tag

- The published-image test must compare the digest of the hash tag against every moving ref.
- Rollout rule: a **missing** `:latest` is a note, not a mismatch — it only exists once a run has
  published that engine. A `:latest` that exists with a different digest is a hard failure.
- Publishing is its own gated step, last: build → verify → push. The push re-checks the flags before
  it tags, so a row cannot reach GHCR with an unverified image.

## Testing the wiring (not just the code)

- Assert step **order** on `run: make …` lines. Workflow header comments name the same commands, so
  `text.index("make test-engine-stage")` happily matches the comment above the job.
- When a Makefile branch changes shape (`serve) make test-engine` → `serve) make test-engine-image &&
  make test-engine`), update the existing assertion to the new contract; do not delete it or loosen it
  to a bare substring.
- New dispatch input? Regenerate the README table: `make dispatch-forms-report`, paste it between the
  `<!-- dispatch-forms:begin -->` / `:end` markers, then `make check-dispatch-forms`.
- Full gate set for an engine-pipeline change: `make openspec-validate NAME=<change>`, `check-engine-params`,
  `check-engine-source`, `check-workflows`, `check-dispatch-forms`, `check-docs`, `check-wiring`, `lint`,
  plus the affected test files in the test image (`docker run --rm -v "$PWD":/workspace -w /workspace
  llgenie/test:latest python -m pytest …`; the host venv has no pytest).

## Watching a dispatched run

```bash
gh api repos/<owner>/<repo>/actions/runs/<id>/jobs --paginate    # job + per-step status
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences
```

- `gh run view <id> --log` returns nothing while the run is still going — per-job logs are the only
  readable form mid-run, and the log endpoint refuses to print without `--allow-escape-sequences`.
- A step appears in the job's `steps` list even when its `if:` will skip it. Decide "did it publish?"
  from the step's `conclusion` (`success` vs `skipped`), never from its presence — that is how a
  build-only dispatch is told apart from a publishing one.
- A forced full sweep is long (fat CUDA/ROCm compiles, `max-parallel: 20`, 240 min/job): poll it from
  a bounded background loop and report the tally, do not hold the session open.
- A sweep row can print `OK image test` and still fail later in the same job (its `version`/`detect`
  step). A zero count of `FAIL` lines is not a green run: read the exit code first, then explain it —
  an `rc=2` with no `FAIL` line is a real defect, not noise.
- The image name is the engine id with `.` → `-` (`llama.cpp` → `llama-cpp`). Normalise before
  matching a params id against an image, registry ref or log line, or every join silently misses.

## Pushing the branch: read the remotes first

`origin` and the fork are not interchangeable in an llgenie checkout — `origin` can be the UPSTREAM
(`asimov-agent/llgenie`) while the fork is a second remote (`fork` → `andyholst/llgenie`). Pushing the
feature branch to the wrong one makes
`gh pr create --repo asimov-agent/llgenie --head andyholst:<branch>` fail with "No commits between …".
Check `git remote -v` (and `git rev-parse --abbrev-ref @{u}`), push the feature branch to the fork, and
delete any branch that landed on upstream by mistake.
