# Converting a prebuilt engine variant to a source build

An engine definition can point at the upstream's own image and never compile
anything. "Build it from source" is then a real change, not a flag flip. This is
the checklist, in the order the failures appear.

## 1. Check the install recipe, not just the flag

`prebuilt: true` is only half of it. Four engines measured on one tree said
"prebuilt" and their install recipes downloaded **compiled artifacts**:

| engine shape | what the install step did |
|---|---|
| release-archive engine | `curl … <project>-linux-<arch>.tar.zst` + checksum + extract |
| pip engine (cuda/cpu) | `uv pip install pkg=={version}` (PyPI wheel); cpu also a `+cpu` wheel from the GitHub release |
| pip engine (cuda) | `uv pip install pkg=={version}` (wheel) |
| vendor engine | `uv pip install pkg=={version}` (wheel) on the vendor torch base |

Flip the flag without replacing the recipe and the image still contains an
upstream binary. A genuine source variant is: checkout at the pinned sha, then the
engine's own build (`cmake`/`make`/`cargo`/`go build`/`pip install` from the
tree).

A tree that already has a full compile block for a *fork* of the engine is the
template — the upstream skill usually carries the same block and only the
container override differs.

## 2. Expect the never-run compile recipe to be broken

A variant that never compiled has a recipe nobody executed. The first real build
is where latent defects surface — budget for it as part of the change.

Measured shape: a flags value joined two groups with a semicolon
(`-DA=ON; -DB=OFF`). Flags are interpolated into ONE shell command, so the
rendered line ended at the `;` and the second group ran as a command:

```
bash: line 1: -DB=OFF: command not found
[engine-runner] FAIL <engine>/<backend>: step exited 127
```

Rules:

- A flag list rendered into a shell line must not contain `;` — join with spaces.
- `grep -rn '; -D' <definitions>` before the first build of a converted variant.
- A trailing verification step in the recipe (`<binary> --help > /dev/null`) is
  what turns a silent bad build into a named failure; keep it.

## 3. Compile on a shared toolchain base, ship only the built tree

The shape that works for compiled variants:

```dockerfile
FROM <shared devel base> AS build          # cmake/ninja/git + CUDA or ROCm devel
… install/compile at the pinned sha …
FROM <slim runtime>                        # e.g. nvidia/cuda:<v>-runtime-ubuntuXX
COPY --from=build <src>/build-<backend>/bin <src>/build-<backend>/bin
COPY --from=build /opt/<tool>/app /opt/<tool>/app
```

The devel toolchain never reaches the shipped image; the runtime base carries
only what the binary links against (`libgomp1`, `curl`, `python3`).

## 4. Prove it per backend, with the pinned sha in the output

Build each backend in turn and read the binary's own version line:

```
make build-engine ENGINE=<id> ARCH=cpu
make build-engine ENGINE=<id> ARCH=cuda
make build-engine ENGINE=<id> ARCH=rocm
make build-engine ENGINE=<id> ARCH=vulkan
make test-engine-image ENGINE=<id> ARCH=<arch>
```

The test must print the version AND name the commit:

```
--version: answers -> version: <x.y.z>-dev (build N, commit <pin8>)   <-- the pin
--help: answers      -h: answers      -V: no answer (invalid argument)
OK image <registry>/<engine>:<pin8>-<imghash>-<arch>
```

- The image tag proves *a* build happened. The commit id proves it built **the
  pin** — assert that, not the tag.
- A documented flag that does not answer is a failure that names the flag; an
  undocumented spelling answering or not is informational.
- Do not claim a backend you did not build. Report the four lines, or say which
  two you ran.

## 5. `available -> no rebuild` is not your compile

The build helper short-circuits when the registry already carries the tag, so a
local "built" line can be a pull:

```
[engine-image] <tag> available -> no rebuild        # the registry's image
[engine-image] built <tag> from containers/…/Dockerfile.<arch>   # a local compile
```

Read which line you got and report THAT. A CI-published image matching your tag
still proves CI compiled the pin, but it does not prove your host did.

## 6. The tests that pinned the prebuilt shape will red — rewrite them

Grep the suite for the retired literals before pushing: the upstream image name
(`FROM ghcr.io/<upstream>/…`), the in-image binary path (`/app/<binary>`), and any
workaround the prebuilt base needed (`LD_LIBRARY_PATH=/app` for an `$ORIGIN`
rpath). Each assertion becomes the new contract: the shared base, the compiled
binary path, the shipped-runtime copy. Deleting them loses the lock; a red unit
job immediately after the conversion is the suite doing its job.

Also re-check the assertions that compare the launcher's binary path — a shim
that resolved `/app/<binary>` now resolves `<src>/build-<backend>/bin/<binary>`.

## 7. Scope by cost, and record the exceptions

Cost is wildly uneven:

- **cheap** — Go or cmake engine with an existing compile block: one session.
- **expensive** — CUDA-wheel Python engine (full kernel recompile): hours per
  backend.
- **likely infeasible** — vendor-built stacks whose own build is multi-hour and
  hundreds of GB.

Measure before enabling one in the sweep. When a build genuinely cannot finish on
a runner, record a **dated decision in the engine definition** (why, and what was
measured) rather than shipping a wheel and calling it source. Keep that exception
visible in the docs next to the engines that do compile.
