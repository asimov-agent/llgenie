# Engine params, binary probes, force-rebuild and publish

How one engine × arch cell goes from a skill to a published image, and the traps at each seam.

## The cell model

```
skills/engines/<id>/SKILL.md
  -> make generate-engine-params [ENGINE=<id>]        # the ONLY step that reads skills
      containers/engines/params/<id>.json            # variant -> backend, arch list, install steps, detect
      containers/engines/dockerfiles/<id>/Dockerfile.<arch>
      containers/engines/binaries.json               # binary path + documented flags + probe policy
  -> make build-engine ENGINE= ARCH=                  # builds from those committed files, no LLM
  -> make test-engine-image ENGINE= ARCH=             # executes the binary INSIDE the image
```

- `ENGINE=<id>` regenerates **only that engine** — a bump must never rewrite another engine's params or
  the shared bases. `make check-engine-params` (0 stale) is the gate; the Dockerfile is a thin wrapper
  that runs `engine_runner.py install params.json`, so the install steps live in the params, not the YAML.
- Build steps are read from the params, so a fix in the skill is invisible until a regeneration.

## Probe policies (`binaries.json`)

| policy | when | what must answer |
|---|---|---|
| `flags` (default) | the CLI is normal | the documented flags **and** the version family (`--version`/`-V`) **and** the help family (`--help`/`-h`) |
| `device` | the CLI initialises a device at import, so no flag can answer on a GPU-less runner | the file must exist; the version comes from the entrypoint's `detect` |
| `help` | the CLI is argparse-only and has **no version flag at all** | the help family; the version comes from `detect` |

Never weaken `flags` because a cell is red. Measure the CLI **inside the built image** first
(`docker run --rm <img> <binary> --version`), then either document the flag the CLI really has or pick the
policy that matches it. A probe that accepts the first spelling that answers is a green lie: run every
member and name the one that failed.

## `detect` must run the binary

A `detect` that echoes the pinned version looks green and lies: an engine's own banner can lag its tag
(a v0.2.4 build still answering `0.1.49`). Prefer the CLI's `--version` when it answers; keep the pin
only as the fallback for a CLI that reports nothing usable, and say which is which in the skill comment.

## FORCE means a real rebuild

- `--force` must pass `--no-cache` **and** drop `--cache-from`; skipping only the "image available"
  check re-tags the previous layers and proves nothing.
- The force must reach the shared base build too (`build_base(…, force=force)`), or a stale toolchain
  silently undermines the engine build.
- The sweep forwards the flag per row; verify with the build log's own `docker buildx build … --no-cache`
  line, not with the exit code.

## Publishing: three names, one owner per moving tag

- immutable hash tag (`<sha8>-<hash>-<variant>`), moving `:<variant>`, and `:latest`.
- `:latest` is claimed by **exactly one** variant per engine (cpu when the engine has one, else its
  only/first variant) so parallel publishing rows cannot race the tag onto another backend.
- Publishing stays gated: verify the binary first, then push, and re-check inside the push step.
- During rollout treat a **missing** `:latest` as a note and a **drifted** one as a failure: compare
  digests of the hash tag, `:<variant>` and `:latest` before declaring the published image good
  (`docker manifest inspect` on each ref).

## Verification that counts

- `make test-engine-image ENGINE= ARCH=` prints the binary's path, then per-flag verdicts, then the
  entrypoint `detect`; a serving cell additionally answers on the OpenAI API.
- A serving test must probe the binary **before** it serves (`… &&  …`), otherwise a cpu cell passes on a
  server whose user-facing binary was never executed.
- From a workflow run, quote the job's own lines (`docker buildx … --no-cache`, `pushed …` per ref) and
  the registry, never the job's green conclusion.

## "From source" is a checked claim

A cell with `prebuilt: false` must (a) contain a real build command (cmake/make/cargo/go/setup.py/install of
 the cloned tree), (b) pin its reference (sha or version tag), and (c) not build `FROM` an upstream build
of itself. Cells that cannot build yet carry a **tracked exception with a reason**, so the gate reds only on
 a new false claim; converting a cell means deleting its exception.

## Diagnosing a red bump PR

1. Read the diff: params, Dockerfiles, skill and the engine's data file are all there → the bump did its job.
2. `DIRTY`/conflicts mean the branch is **stale**, not wrong: rebase it and re-run; the fresh base usually
   carries probe/detect fixes the branch predates.
3. A "byte-stability" test asserting the previous pin's data shape is a **test** defect: state the
   invariant (a family is hostable-or-explicitly-not) and derive expectations from the pinned upstream
   file, not from a literal map.
4. Then verify the pin end to end — build the image, run its binary, read `detect` — before calling the
   bump green.
