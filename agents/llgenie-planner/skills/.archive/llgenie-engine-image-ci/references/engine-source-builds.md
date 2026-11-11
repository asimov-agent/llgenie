# Engine source builds, the dispatched sweep, and local per-arch verification

Who builds what, when a variant compiles, and how to verify it with real output instead of
reading a generated Dockerfile.

## Who builds what (do not conflate these)

- **`ci.yml`** builds only the images a PR **changed** (`CHANGED=<base>`). That is the merge gate;
it is not a full sweep.
- **`engine-bump`** (weekly) is deterministic: pin → `derive` (git/regex parsing, no LLM) → apply →
`make generate-engine-params`. After it, a Hermes review leg (`engine-params-review`) proposes only
flags whose flag **and verbatim quote** appear in the upstream file at the pin; the host validates
and drops anything else before writing.
- **The build is CI**: `engine-image` matrix rows call `make build-engine ENGINE=… ARCH=…` then
`make test-engine-stage ENGINE=… ARCH=… TEST=serve|detect`.
- **`.github/workflows/engine-build.yml`** is the on-demand full sweep: `workflow_dispatch` only
(`engine`, `arch`, `push`), rows from `make engine-build-matrix`.

No Hermes agent builds an image. An agent reviews/proposes parameters; CI compiles them.

## The scopes are one list

```
make engine-build-matrix [ENGINE=] [ARCH=]   # JSON rows from the committed params (the workflow's only source)
make build-engines                           # every engine x variant, parallel (JOBS=, default nproc)
make build-engines ARCH=cuda                 # one arch, every engine
make build-engines ENGINE=vllm               # one engine, every arch type
make build-engines ENGINE=vllm ARCH=cuda     # one engine x one arch
```

Every row carries its own parameters (`containers/engines/params/<id>.json → variants.<arch>`:
`arch`, `build_args`, `install`, `binary`, `detect`). Nothing is shared between engines or backends.

## Verify by BUILDING, per arch — never by reading the params

```
make build-engine ENGINE=<id> ARCH=<arch>
make test-engine-image ENGINE=<id> ARCH=<arch>
```

The `detect` output must name the **pinned sha** (`0.7.0-dev (build …, commit <pin8>)`). A version
string without the pin proves an upstream/prebuilt binary, not your build. Report the real output;
"the params look right" is not verification.

`available -> no rebuild` in the build output means that tag already exists and was **pulled** —
usually because CI published it for this commit. That is not a local compile; say so, and pick
different rows when the point is to prove the recipe.

Undocumented short flags are reported but may not fail the probe: the policy requires the flags the
skill documents. A `-V: NO ANSWER (invalid argument)` line next to a passing run is expected output,
not a silent skip — quote it.

## Prebuilt → source conversion traps

- **`prebuilt: true` is only half the story: read `install:` before believing a variant can build.**
Some skills fetch a compiled artifact in the install recipe itself — a release archive
(`ollama-linux-*.tar.zst`), a PyPI wheel (`vllm==`, `sglang==`, `tensorrt_llm==`), a `+cpu` wheel from
a GitHub release. Flipping the flag on those yields an image that still contains an upstream binary.
A variant converts in minutes only when its skill already carries clone-at-pin + build steps
(cmake/go/pip-from-checkout); otherwise the recipe must be written first, cheapest engine first, and
the heaviest vendor build may honestly end as a dated decision in the skill.
- `prebuilt: true` also means the derived params are
**metadata only** — the install/cmake path has never run. Converting a variant to source
(`container: {<backend>: {runtime: true, runtime_copy: ["{build}/bin"]}}`) therefore exposes latent
breakage. Build it immediately.
- **Shell metacharacters in skill flag strings break the rendered command.** Flags are joined with
spaces; a `;` inside `cmake_flags.common` splits the rendered `cmake` line and the next flag runs as
a command (`bash: -DXXX=OFF: command not found`, exit 127). Check every flag string for `;` when
touching a build recipe.
- **A design flip reds the tests that pinned the old design.** After converting, grep the test tree
for the old literals (`ghcr.io/ggml-org/…`, `/app/<binary>`, `LD_LIBRARY_PATH=/app`) and rewrite
those assertions to the new contract. A `linux / unit` red immediately after such a change is the
suite encoding the old design, not a flake.

## Publishing order in the dispatched sweep

A sweep publishes only **after** the binary test: `make build-engine` (no `PUSH=`), then
`make test-engine-stage`, then `make push-engine` as its own step gated on the dispatch input.
`make build-engine PUSH=1` publishes from inside the build, so a binary that does not answer can
reach GHCR before anything tested it. `push-engine` re-checks the binary's flags itself, so the
ordering is the belt and the target is the braces. Assert the order on the `run:` lines, not on the
file text — the header comments name the same commands and make a naive `text.index()` compare pass
or fail for the wrong reason.

## The dispatched workflow must copy the guard verbatim

`tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical` requires every workflow's
guard step to be byte-identical. Copy the whole `guard:` block from an existing workflow file rather
than retyping it (a reworded comment inside `run:` is enough to red it).

## Running one test module from a git worktree

`make test-unit` mounts the parent `.git` for you (`WORKTREE_MOUNT`, derived from the worktree's
`.git` file). A hand-run `docker run -v "$PWD":/repo` does **not**, so git-reading tests fail with
`fatal: not a git repository: <parent>/.git/worktrees/<name>`. Mirror the Makefile:

```bash
parent=$(sed -nE 's|^gitdir: +||p' .git | sed 's|/.git/worktrees/.*||')
docker run --rm -u root -v "$PWD":/repo -v "$parent:$parent:rw" -w /repo llgenie/test:latest \
  python -m pytest tests/<module>.py -q
```

Inside such a container, git also needs `git -c safe.directory=<repo>` (root owns the mount).

## OpenSpec change dirs are root-owned

`make openspec-new` writes `openspec/changes/<name>/` as root inside the container, so the first
`write_file` there is denied with EACCES. `sudo` cannot prompt in a background shell; chown through a
container instead:

```bash
docker run --rm -v "$PWD/openspec/changes":/c alpine chown -R "$(id -u):$(id -g)" /c/<name>
```

## Report what the build said, not what the params imply

When the user asks whether the bots "really" build an engine, answer with the command and its real
output (image tag, `commit <pin8>`, flag verdicts), and state plainly which actor builds (CI, not an
agent). Reading `params.json` or a generated Dockerfile is not evidence, and a claim of "green"
without a per-arch build is rejected.
