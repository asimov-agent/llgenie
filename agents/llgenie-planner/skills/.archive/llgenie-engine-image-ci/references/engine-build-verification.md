# Building and verifying every engine × arch cell

Goal: prove that each inference-server engine image is **built from source at its
pinned sha, for its own backend/arch, with its own parameters**, and that the
resulting binary actually runs.

## Where the parameters live

- `containers/engines/params/<id>.json` → `variants.<backend>` carries `arch`
  (e.g. `75;80;86;89;90;120`, `gfx1030;…`), `build_args`, `install` (the real
  compile steps), `env`, `launch`, `detect`, and `prebuilt`.
- `containers/engines/dockerfiles/<id>/Dockerfile.<backend>` is generated from
  that, one per engine × backend.
- `containers/engines/binaries.json` carries, per cell, the `binary` path, the
  `flags` it documents, and the `probe` policy — read by the post-build probe,
  never hashed into the image tag.
- Everything is written by `make generate-engine-params` from the skill; never
  hand-edit params or Dockerfiles. `make check-engine-params` fails a commit
  whose generated files are stale.

## Commands (one list, four scopes)

```
make engine-build-matrix [ENGINE=] [ARCH=]        # JSON matrix the CI sweep builds
make build-engines                                # every engine x every variant, parallel
make build-engines ARCH=cuda                      # one arch, every engine
make build-engines ENGINE=llama.cpp               # one engine, every arch it supports
make build-engines ENGINE=llama.cpp ARCH=cuda     # one cell
make build-engines ... VERIFY=1 JOBS=3            # also run each built image's binary test
make build-engine ENGINE=… ARCH=…                 # one cell, build only
make test-engine-image ENGINE=… ARCH=…            # probe the binary's flags (version/help families)
make test-engine-stage ENGINE=… ARCH=… TEST=serve|detect   # CI's per-cell test
make push-engine ENGINE=… ARCH=…                  # publish AFTER the probe passed
```

Rows come from the committed params (via `scripts/engine_image.py matrix`), so a
new variant is in the sweep as soon as its params are committed — never keep a
hand-written roster next to it.

## `prebuilt: true` is only half the story

Before claiming a cell is "built from source", read its `install` steps. Some
engines' recipes fetch a compiled artifact even with `prebuilt: false`:
`curl … ollama-linux-*.tar.zst` (a release archive), `uv pip install vllm==…` /
`sglang==…` / `tensorrt_llm==…` (published wheels). Converting those cells is
**writing a build recipe** (clone at the pin + the engine's own build), not
flipping a flag. Say so instead of promising a one-line change.

## A prebuilt variant's compile recipe has never run

`prebuilt: true` short-circuits the install steps, so their bugs are invisible
until the cell is converted. Build the converted cell **before** trusting it, and
check the rendered command for shell separators inside a flag string: a `;`
between two groups of `-D…` flags cuts the rendered `cmake` line and the tail is
executed as a command (`bash: -DLLAMA_BUILD_TESTS=OFF: command not found`, exit
127). Flags are space-joined; never `;`-join them.

## Conversion checklist (per cell)

1. Read the skill's `install` block — does it compile, or download?
2. Point `container:` at the shared devel base and ship only the build output on
   the slim runtime base (`runtime: true`, `runtime_copy: ["{build}/bin"]`);
   drop the upstream `base:`/`prebuilt: true`.
3. `make generate-engine-params ENGINE=<id>` (scopes to that engine; a bump must
   never rewrite another engine's params or the shared bases).
4. Grep the **test tree** for the old contract before running the suite: the
   upstream `FROM …` base, the `/app/<binary>` container path, and any
   `LD_LIBRARY_PATH=/app` workaround all encode the prebuilt design and will red
   the unit job. Re-point those assertions at the source build (built path,
   shared base, no workaround); do not delete them.
5. `make build-engine ENGINE=… ARCH=…` then `make test-engine-image …` — quote
   the `commit <sha>` from `--version`; it must equal the pin.
6. Repeat for every arch of that engine, then `make build-engines VERIFY=1` for
   the rest of the matrix.

## Publish only after the binary answered

Order per cell is **build → verify → publish**. A build step that publishes
(`make build-engine … PUSH=…`) can put an untested image in GHCR; publish with
`make push-engine`, its own step, gated on the dispatch input and after the
probe — `push-engine` re-checks the binary's flags before pushing.

`make test-engine-stage TEST=serve` must run `test-engine-image` **first** and only
then `make test-engine`, joined with `&&`: a cpu cell that jumps straight to
serving never proves the file a user actually runs. When a test asserts that
order, compare the indexes of the **`run:` lines** — the workflow header comments
name the same make targets and match a naive `text.index("make test-engine-stage")`
first.

## `prebuilt: false` is checked, not asserted

`make check-engine-source` (`scripts/engine_source_guard.py`, in `ci-unit`) reads
the committed params and fails a source cell that (1) runs no build command
(cmake / make / cargo build / go build / `pip install <tree>` / `setup*.py` /
`get_llama_cpp(...)`), (2) clones an **unpinned** reference (a branch instead of a
sha or version tag), or (3) has a generated Dockerfile whose first `FROM` names
that same engine — the `prebuilt: true` lie in another place. `llgenie/base-*`
toolchains are fine; backend words are not engine names, so `rocm/pytorch` is a
legitimate base for `<engine>-rocm`.

Cells with no source build yet live in `KNOWN_NOT_SOURCE` with a reason and an
issue, the way `DISABLED` works: printed on every run, failing only when a **new**
cell claims a build it does not have. Converting a cell = deleting its entry.

## Reading a sweep that failed

`make build-engines … VERIFY=1` fans out with `xargs -P`.

- **`rc != 0` with zero `FAIL` lines is still a failure.** Count the
  `OK image test` lines against the committed cells, then grep the log for
  `*** [Makefile`, `Traceback`, `Error 1` — the failing invocation names its
  target (`build-engine` / `test-engine-image`), and the real cause has been the
  engine's own `detect`, not the build.
- Cells in `DISABLED` are never emitted by `matrix(ci=True)`, so committed cells
  and CI rows are different numbers; say which one you mean.
- `available -> no rebuild` is a cache hit, not a verification.
- A fix in a shared skill (a probe policy, a `detect`) affects sibling cells, and
  a re-run is cheap once the images exist: re-run the whole sweep, not the one
  cell.

## `grep -q` in a step is a SIGPIPE trap

Every install/detect step runs as `bash -euo pipefail -c "<step>"`. In
`{binary} --help 2>&1 | grep -q '^strata ' && echo {version}` the `grep -q` exits
at the first match, the engine takes SIGPIPE, and `pipefail` reports **141** — the
image passes the binary probe and then `docker run <image> version` says
`missing (detect exited 141)` for a perfectly healthy binary. Use plain
`grep … > /dev/null` (it reads to EOF), and keep a test that refuses any skill
containing `grep -q` and asserts the detect still echoes the pinned version.

## Probe policies (`binary_probe`)

- default `flags`: every documented flag must answer, and both the help family
  (`--help`/`-h`) and the version family (`--version`/`-V`) must be answered by
  one spelling each.
- `device`: the CLI initialises its device at startup and cannot answer on a
  device-less runner; the version comes from the image's `detect`.
- `help`: a parser with **no version flag at all** (argparse-only CLIs such as
  `mlx_lm.server`). The help family must answer; the version comes from
  `detect`. Without it the probe fails an engine for a flag it never had.
  `probe_policy()` in `scripts/engine_skills.py` passes both `device` and `help`
  through to `binaries.json`.

## New dispatchable workflow mechanics

- Copy the guard job from an existing bot workflow **verbatim**: a repository
  test compares every guard step byte-for-byte, so a re-worded comment reds it.
- Regenerate the README dispatch table with `make dispatch-forms-report` and
  paste it between the `dispatch-forms` markers; `make check-dispatch-forms`
  fails a stale table or an undocumented input.
- Every new target needs a `##` help line, a `.PHONY` entry and a README mention
  (`make check-docs`, `make check-wiring`).
- A sweep belongs in its own `workflow_dispatch`-only file, not in `ci.yml`:
  `ci.yml` keeps building only the images a PR changed, which is the merge gate.

## Local test caveat (worktrees)

Run the suite through `make test-unit`, not a hand-typed `docker run`: a
worktree's `.git` is a file pointing at the parent checkout's
`worktrees/<name>` path, so a bare `docker run -v <worktree>:/workspace` makes
git answer "not a git repository" (and running as root adds "dubious
ownership"). The Makefile's `TEST_OPTS` mounts the parent `.git` for exactly
that reason; if you must use raw docker, mount it too.
