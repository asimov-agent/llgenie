# Producer-owned install seam (`make test-engine-install`) + the make-seam gate discipline

When an owner directive moves a consumer test INTO the producer ("the build/publish engine runs these
tests accordingly instead"), install-test each freshly built+pushed engine image per matrix row, in the
pipeline that owns the build. The row-exact seam is tighter than a whole-backend sweep: a row's leg
proves THAT row's image installs.

## The seam (what worked)

`engine-build.yml` matrix row currently runs `build-engine → test-engine-stage (TEST=serve|detect) →
push-engine`. After publishing, add TWO legs — a SERVE leg then an INSTALL leg — gated on the same
publish condition so they only run when the row actually published an image:

```yaml
- name: "serve-leg: make test-published-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }} …"
  if: ${{ matrix.engine != 'none' && inputs.push == 'true' }}
  run: make test-published-engine ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}
- name: "install-leg: make test-engine-install ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }} …"
  if: ${{ matrix.engine != 'none' && inputs.push == 'true' }}
  run: make test-engine-install ENGINE=${{ matrix.engine }} ARCH=${{ matrix.variant }}
```

**The install-leg only VERSION-checks the binary; it is not the "serve" verification of the published
image.** `test-built-engine` proves every installed launcher runs the binary and prints a version — the
SUBSET of publish verification that the pre-push stage already proved on the BUILT image. To still
verify the PUBLISHED image really serves (the role of the old `published.yml`/`engine-published-test`
surface), keep a separate SERVE leg that pulls the just-published image (`make test-published-engine`: pull
with digest == `:ARCH`, re-check the binary version, then serve/answer "hi" on cpu-fallback rows;
GPU-only rows get the version test via `--no-gpu` because the gpu-less runner cannot serve them). Folding
published.yml into the producer WITHOUT this serve-leg silently drops "does the published image serve"
down to a version check — the published binaries must be genuinely exercised, not a ceremony.
So the post-publish chain is `push-engine → test-published-engine (serve-leg) → test-engine-install
(install-leg)`, and the published binary is exercised pre-push (flags), post-push (serve/version) and
install (launcher-version).

Back it with a single deliberately-internal make target that reuses the existing install pieces — do
NOT hand-roll a third surface:

```make
test-engine-install: bash-check   # NO `##` help line — make it deliberately internal
	@test -n "$(ENGINE)" || { echo "Usage: make test-engine-install ENGINE=<id> ARCH=<variant>"; exit 1; }
	make engine-install ENGINE="$(ENGINE)" BACKEND="$(ARCH)"   # install the row's just-published image
	make test-built-engine
	make ci-install-dry
	make ci-install-uninstall
```

A `ci-engines BACKEND=` whole-backend leg installs every engine of a backend; the row-exact
`engine-install ENGINE= BACKEND=` proves THAT row's image installs, which is the producer-owned property.

**`engine-build` is the SOLE producer — ci.yml builds, tests and installs NO engine.** An owner directive
can consolidate the whole engine pipeline into the producer (remove `engine-image` / `engine-published-test` /
`linux-published` + `published.yml` from ci.yml), so there is exactly one producer and one place the install
leg lives.

**ci.yml's install row must be PRODUCT-ONLY.** `make install` (the user-facing command) pulls the host's
backend engine images and version-tests them — `install = bash-check venv-install engine-launchers link
test-built-engine smoke`, where `engine-launchers` (pull + write `~/bin/engine-*` start scripts) and
`test-built-engine` (version the engines) are exactly the engine test the directive moved into the producer.
So ci.yml's `make ci-install` chain must NOT run `engine-launchers` / `test-built-engine`, must NOT wait for
engine images (`ci-wait-engine-images`), and must NOT run `make install` (`ci-install-run`). Add a
`ci-install-product` target (`venv-install link smoke`) and drive only that + `llgenie --dry`/`--dry-args` /
`uninstall` from ci.yml. Keep `ci-wait-engine-images` / `ci-install-run` only as host/macOS-facing make
objects, not exercised by ci.yml. Pin it: the ci-shape tests must assert `ci-install` contains
`ci-install-product` and NO `ci-wait-engine-images` / `ci-install-run`.

**A ci-install* / product-make stage that builds a venv or needs the pinned interpreter must run INSIDE
the test container (`$(ENGINE_TEST_RUN) sh -c …` on Linux), never on the bare runner.** The repo's pinned
Python 3.11 exists only in the `llgenie/test` image; the bare ubuntu runner has only its default python, so a
`ci-install-product` that ran `venv-install` directly failed exit 2 with "python 3.11 … none was found" the first
push. Mirror the OS branch the other `ci-install-*` stages use — macOS runs the venv directly, Linux wraps every
step in `$(ENGINE_TEST_RUN)` — and verify with `make -n ci-install-product` that it resolves to a `docker run …
llgenie/test`. Same rule for any new product-install/venv-building stage added to a reusable pipeline.

**Re-pointing a shape test at a differently-shaped owner: drop the assertions that no longer apply, and
never assert the absence of a token that appears in the new owner's OWN docstring.** When the ci install row
went product-only, `ci-install-run`'s OS-branch asserts (`ifeq $(HOST_OS),Darwin` / `$(ENGINE_TEST_RUN)`) had
to move to `ci-install-dry`, which HAS them — `ci-install-product` is OS-neutral (`venv-install link smoke`)
and asserting "Darwin not in prod" tripped on the word in the target's own `#` comment. Assert what the new
owner's recipe actually DOES (the product targets present, the engine targets absent); read the
`mk.split("\n<target>:", 1)[1]` block including its comment header, and keep negative substring asserts to
tokens that cannot appear in the comment itself (`engine-launchers`, `test-built-engine`) rather than loose
words.

**A step/workflow `name:` with a colon-space is illegal unquoted YAML** (`PRODUCT-ONLY: install` → "mapping
values are not allowed"); spell it with a hyphen, or the workflow won't parse.

**Flow / step / make-target comments must name EVERY step the leg actually runs.** `test-engine-install` is
`engine-install` + `test-built-engine` + `ci-install-dry` + `ci-install-uninstall`; describing it as "install +
dry + uninstall" silently hides the installed-binary version check. A flow comment, a step `name:` and the
make-target `#` line must list the real steps, or a reader takes a weaker check for a stronger one. Fix the
sentence that misled; don't append "actually it also…" beneath it.

**The producer matrix builds/publishes EVERY arch (cpu/cuda/rocm/vulkan) for every engine by default — `none`
is the empty-matrix placeholder, never a real build.** CI is a GPU-less x86_64 runner, so the build/publish does
not care which arch a host will run. The host picks its arch at install/run time (`variant_for` / backend
detect pulls the already-published image for the matching arch); the engine-build pipeline is not host-arch
gated. The `matrix.* != 'none'` gate only skips the placeholder injected when a filtered matrix would be empty
so GitHub doesn't fail it; the default sweep is one row per engine×arch, run in parallel.

## The make-seam gate discipline (all four gates must be rc=0)

- **`check-docs`**: a new `## ` help line classes the target as USER-FACING and requires documentation
  (or a docs-exceptions entry). A CI-internal seam carries NO `##` — a single `#` comment instead
  (`test-unit-network` / `engine-matrix-pushed` precedent).
- **`check-wiring`**: a phony target (one that produces no file of its own name) must be added to the
  `.PHONY:` block, or check-wiring reds "target not declared .PHONY: shadows…".
- **A whole-chain skip is a `make`-level conditional, never an inline `exit 0`.** Each `make` recipe LINE
  runs in its own shell, so `exit 0` on one line stops only that line and the rest of the recipe still runs
  (the classic trap: the install leg "skip" still executed `engine-install`). When the leg must skip if this
  run published nothing (a PR/none row), gate the WHOLE chain with `ifeq ($(PUBLISH),1) … else … endif`
  and pass `PUBLISH` in as a make var — decide the event inside make, not in the workflow step.
- **The step-`if:` is row-gate only — `test_no_ci_step_or_job_is_skipped` enforces it.** A step `if:` may
  only be the row placeholder (`matrix.* != 'none'`), `always()`/`failure()`, a platform Docker gate, or the
  macOS openspec CLI. Putting `github.event_name == 'push'` (or any event gate) directly in a step-`if:` reds
  that pin. Pass the event as a make var (e.g. a `PUBLISH` env set from the run's event) and decide inside
  make; keep the workflow step row-gated only.
- **`check-workflows`** validates the edited workflow YAML parses; **`check-dispatch-forms`** confirms a
  dispatchable workflow still states its work and inputs (an install-leg step alone changes neither).
- **Pin the new step**: extend `tests/test_engine_build_workflow.py` with a fail-closed test asserting
  the install-leg runs AFTER `push-engine` and that `test-engine-install` wraps the four install/dry/
  uninstall targets — so a later edit cannot silently drop the producer-owned install test.
- Run the new pin test and the surrounding workflow tests to GREEN before committing.

## Coordination (workflow-ownership split)

When a separate lane owns the consumer workflow files (`ci.yml`/`published.yml`), agree the shared
branch name + one-PR-with-both-halves before either cuts. Opening the additive engine-side half first
is safe because the consumer's removal (the old tag-poll install surface) is still on main — no untested
gap. Flag the counterpart to push their removal onto the SAME branch; the removal must never outrun the
addition.
