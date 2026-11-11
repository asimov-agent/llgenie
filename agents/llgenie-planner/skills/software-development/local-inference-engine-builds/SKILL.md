---
name: local-inference-engine-builds
description: "Build/serve local-LLM engines per GPU (llama.cpp, vLLM)."
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llm, inference, llama.cpp, cuda, rocm, metal, cpu]
---

# Local inference engine builds

Building a local-LLM engine (llama.cpp and forks, Ollama, vLLM, SGLang, MLX,
TensorRT-LLM, …) is not a single recipe — the parameters that make it fast and
correct depend on the HOST hardware, and differ per engine. The general method:
for each engine read ITS upstream install/build docs (it can rename flags,
change supported backends, or drop releases), then encode the result in a
machine-readable per-engine definition the install runner resolves against the
REAL host. Never assume a remembered flag name or a remembered install command
still holds.

## The hardware parameter axis (the part that costs real time)

For every engine, the per-backend build/install parameters derive from the
actual hardware probed on the host, not from a fixed flag string:

- **CUDA**: from `nvidia-smi --query-gpu=compute_cap` (e.g. `8.9`) to
  `-DCMAKE_CUDA_ARCHITECTURES=`/`TORCH_CUDA_ARCH_LIST` by joining the two digits
  (`8.9`→`89`). Pick CUDA wheels by the installed toolkit/driver version, and
  honor each engine's minimum compute capability (vLLM needs ≥ 7.0, etc.).
- **ROCm**: from `rocminfo`/`hipcc` GPU name (e.g. `gfx90a`/`gfx1100`) to
  `AMDGPU_TARGETS`/`GPU_TARGETS`/`PYTORCH_ROCM_ARCH`, and know which gfx targets
  each engine supports (older cards need flag-based overrides). Many engines are
  CUDA-or-Metal-only: an engine with no ROCm backend just cannot run on AMD
  cards — detect that up front instead of trying build flags that don't exist.
- **Metal**: macOS + `arm64` only. Tune unified-memory wired limits
  (`sysctl iogpu.wired_limit_mb`) for larger models, and respect Apple-Silicon
  generation constraints.
- **CPU**: a portable baseline build (`GGML_NATIVE=OFF`, no arch pin) is what a
  CI cache can reuse across different runners; `-march=native` SIGILLs on a
  different CPU. On the local host you may allow native tuning.

Build flags are CONDITIONAL on these probes: a flag whose condition is
unsatisfied (no GPU → no `CMAKE_CUDA_ARCHITECTURES`) drops out of the command.
Keep the rule "explicit hardware → engine registry → engine map → keyword →
default" so an engine with no explicit hardware text (or a blank/absent
backend) falls to the right default instead of silently landing on CUDA.

## Serving the OpenAI-compatible endpoint

- Every servable engine either ships an OpenAI-compatible server or must be put
  behind one; the model is exposed under ONE alias (e.g. `llm-local`) that the
  launcher/health check calls. `--served-model-name` (vLLM/SGLang), a Modelfile
  `FROM` for Ollama, etc. — the flag differs per engine, and SOME engines have
  NO alias flag at all: they read extra model names from an `aliases` list in
  their own config file (Strata's `serve/server.py`). For those, the launch
  command must write the alias into the config (idempotently — don't add it
  twice) and pass only the arguments the server actually accepts. Grep the
  server's `argparse`/`--help` before assuming a flag exists.
- Confirm the health endpoint and `/v1/*` support in the engine's own docs.
- **Mark non-servable engines explicitly** (`servable: false`): browser-only
  (WebLLM), library-only, or benchmark-only engines have no HTTP endpoint and a
  health check against them will never pass. Record what they CAN do instead of
  pretending they serve.
- Verify the REAL Metal/CUDA path on the host (a container CPU health check
  proves the code, not the hardware path) and record it before claiming an
  engine works.

## Testing install/uninstall and interactive serving on the host

When the deliverable is a CLI that `make install` writes into the user's `~/bin`
(and `make uninstall` removes), test the full cycle on the REAL host, not just
in a container:

1. **Back up the existing launcher before `make install`.** Copy `~/bin/<tool>`
   and its symlink target to a scratch dir first. The old install may point at
   a different checkout than the one you are testing. After `make uninstall`,
   LEAVE the new install in place by default — the user usually wants to try it
   themselves. Only restore the backup when the user explicitly asks to go
   back to the old setup (and say the backup's path + that the scratch dir is
   pruned, so they know it is not permanent).
2. Run `make install`, then verify the launcher runs (`<tool> --list` or a
   smoke test) and that `test-built-engine`/version checks pass.
3. Drive the interactive picker through a pty (stdlib `pty` in a small helper,
   no new deps): `expect` the `Pick model [1]:` and `Pick inference server
   [1]:` prompts, send a selection, then poll the `/v1/models` endpoint until
   the model is up and answer a real `/v1/chat/completions` request. This
   proves the interactive path end-to-end.
4. Run `make uninstall`, confirm the bin files are gone and no engine
   containers remain, then restore the backup.

## Testing the model → engine → quant pick matrix (arch × vram × ram)

When the launcher's picker must always reduce "how much VRAM/RAM/arch I have" →
"this model" → "this inference server" → "this exact quantized HF file", test the
WHOLE permutation set, not fixed cases. Drive one `matrix(registry, gb, ram_gb,
arch)` function over an exhaustive (arch × VRAM × RAM) grid — `cuda|rocm|vulkan|metal|cpu`
× {8,16,32,64} × {16,32,64} — and assert, per cell, that every runnable
model×engine maps to a resolvable `https://huggingface.co/<repo>/resolve/<rev>/<file>`
and that the quant is the largest one within the budget. This is how the CI proves
arch selects the server: a cuda-only engine never appears off-cuda, a Vulkan/CPU-absent
engine only on cuda/rocm, and a Metal host never falls back to a cpu image.
Make the arch (and VRAM/RAM) overridable at the CLI (`--vram V --ram R --arch A`,
flags taking precedence over positionals which override the detected host) so CI
can drive the grid as an asserted, reproducible command.

**Drive the REAL registry, not a synthetic fixture.** A permutation test built on
a hand-made fake registry misses the real edges (an engine that only serves
sharded models, a model with one supported engine, an MoE whose quants all
outgrow a small card). Read the vendored `data/models.json` so every trending
model × every engine it can run × arch × vram × ram is enumerated; stub ONLY the
Hub *tree* (a deterministic quant ladder per repo, exact sizes, no network) so
the expected URLs are stable and CI-fast. A stubbed tree with synthetic sizes is
fine for the logic tests — but then the resolvable-file check must use the LIVE
Hub (below). Parametrize with readable ids (`model::engine::arch::vV::rR`) so the
ENTIRE parameter list of every variant is visible in the pytest report; the user
will ask for exactly this when they say "show me all the variants you are going
to test."

**Split hermetic-logic from live-existence into two test classes.** The matrix
logic (offered iff arch has a runnable image AND a quant fits the budget; largest
quant that fits; resolvable URL *shape*) is hermetic — stubbed tree. Whether the
expected `https://huggingface.co/<repo>/resolve/<rev>/<file>` actually exists is a
distinct, real question: probe the LIVE Hub tree and assert each planned file
answers HTTP 200/206 on a ranged GET (1-byte request, no full download). One test
class proving logic + one proving existence is easier to keep green independently,
and the user's requirement "the expected link must be asserted to exist (200)"
means the live check is mandatory, not optional.

**The offered-engine contract is "arch runnable AND a quant fits budget", per
engine, not "every fitting engine is offered."** A model can have a row because
ONE engine fits (e.g. a 7 GB own-checkpoint engine) while the GGUF-only engines
have no cell on that row because every GGUF quant exceeds the budget. The test
must assert per (model, engine): offered ⟺ engine has an arch image AND some
quant ≤ weight_budget_gb; a model whose VRAM tier exceeds the card is excluded; a
model that fits but with no offered engine is reported skipped-with-a-reason,
never silently absent.

- **Own-checkpoint engine stubs MUST be budget-aware, exactly like the real plan
  functions.** If the stub `tensorfold_plan`/`strata_plan` returns its fixed plan
  regardless of budget, the matrix OFFERS its engine on a card whose budget is
  smaller than that plan — then the largest-quant-that-fits invariant fails for
  the wrong reason (the stub defied the budget), not because the picker is wrong.
  Mirror the real signature: return the plan only when its size ≤ the budget it
  is given (else `None`, the "smallest quant exceeds budget" skip path), and make
  the expected-fit helper use the SAME budget rule so the test's expectation and
  the stub agree.
- **A registry keyed by engine NAME but consumed by engine ID is a KeyError
  trap in a matrix test.** Build the engine stub as `name -> {id, variants,
  formats}` (what the registry lookup uses) but the picker emits each engine's
  `id`; assert variant validity through an `id -> variants` map rebuilt from the
  stub, or any lookup by id raises KeyError. Write the id→variants map once
  (`VARIANT_BY_ID = {info["id"]: info["variants"] ...}`) so arch-variant
  assertions and the per-arch rules share one truth.

**End-to-end use cases belong in the suite, not just the inner function.** The
user will demand the REAL script's business logic (the python files that run the
pick) is asserted from the use-case level with the engine start MOCKED — a
function-level `matrix()` test is not enough. Spawn the actual launcher
(`scripts/llgenie_serve.py`) as `llgenie --pick <model> --engine <engine> --dry`
for every declared (model × engine × arch) and assert it stars the engine's
arch-variant image, plans a real HF download, and prints the start-script
command — `--dry` returns BEFORE the start script's `os.execv`, so the whole
pick runs end-to-end without ever starting an inference server. This is the
shape of a "use-case level" requirement.

- **A CLI subprocess resolves the LIVE Hub; judge `offered` from the same live
  source, never an in-process stub.** The stubbed Hub tree only exists in the
test process — the spawned CLI reads the real network. If you compute
`expected_offer` from the stub but the CLI decides against the live tree, the
two disagree and you debug a phantom mismatch. Compute the expectation from
the live `matrix()` too (or from the CLI's own output), so function-level and
use-case-level test the same data.
- **`--engine <name>` is a SUBSTRING match against both id and name, and the
  CLI picks one winner by t/s ranking — never assert a literal
  `Engine : llama.cpp [rocm]`.** The requested `llama.cpp` may resolve to
  `llama.cpp (LaurentZuijdwijk fork) [rocm]` (the fork contains the substring
  and ranks higher on that arch). Assert the requested name appears in the
  `Engine :` line and that the line carries a `[variant]` bracket; assert
  `would download <repo>/<path>` and a `llgenie-engine-<id>` start script were
  printed. That proves the full use case ran without pinning an engine the
  ranking may not choose.

## A registry engine with no skill has no image (the chain that silently hides models)

When the engine list comes from a vendored registry (a trending/local-LLMs store), a newly
listed engine becomes servable only through this chain, each link generated from the one
before it:

`engines[]` in the registry → `skills/engines/<id>/SKILL.md` → `make generate-engine-params`
(→ `containers/engines/params/<id>.json` + one Dockerfile per engine × arch) → the
`engine-image-*` matrix in CI (build, test, push).

- **The image matrix is derived from the params, so a new engine needs NO workflow edit.** Once
  the skill exists and its params/Dockerfiles are generated and committed, CI builds and
  publishes every declared backend automatically. Do not add per-engine jobs by hand, and do not
  "fix" a missing image in the workflow — the missing file is the skill.
- **No skill means no image means the engine is dropped from the offer, silently.** Ranking keeps
  only engines with an image variant, so the models whose only engine is unskilled disappear from
  the trend list instead of showing up as work. That is why every unresolved engine must become
  either a shipped skill or a dated, reasoned decision in the unsupported list — and why the
  omission has to be enumerated (an engine→status report), never assumed.
- **Scaffold the skill from the registry entry and leave what you cannot prove EMPTY.** Generate
  the file from the facts the registry states (engine name, repo URL, backends parsed from a
  string like `CUDA / ROCm / CPU / Metal`) and write `ref`, `pinned`, `verified`, `license`,
  `formats`, `prereqs`, `install.<backend>`, `binary`, `detect`, `launch`, `health`, `alias_mode`
  as empty values. A guessed pin or apt package is worse than an empty one because it BUILDS; the
  repo's own validator reports an empty required key as `missing <key>` / `needs <key>`, so the
  scaffold gets an ordered to-do list for free. Give it `--dry` and `--force`, and make an
  out-of-tree `--out`/`REGISTRY` knob REAL: verify the make target forwards the variable — a
  silently dropped one turns a preview into a write into the real skills tree.
- **A failed backend parse must fail loudly.** When the registry's backend wording names nothing
  the skill vocabulary knows, refuse and name the string plus the explicit override; never default
  to CUDA — that is how a ROCm-only engine lands on a CUDA image nobody can run.
- **The tracking issue filed for a new engine must name its first command** (the scaffold target,
  its id/backends knobs, then the validate and generate-engine-params targets). A bot that picks
  the issue up otherwise starts from a blank page and re-derives the required key set from the
  parser source.

### Who owns each link (two different bots — do not conflate them)

- **The registry-sync bot carries a NEW engine; the engine-bump bot only re-pins engines that already
  have a skill.** The bump derives from an existing `skills/engines/<id>/SKILL.md`, so it can never
  create one — answer "which bot adds the new engine to the list" with the sync bot, and "which bot
  regenerates the params/Dockerfiles" with whichever step runs `generate-engine-params` (the sync's
  follow-up skill PR, or the bump for an existing engine). Conflating them sends the work to a bot
  that has no code path for it.
- **Order of the new-engine flow, and the gate at each step:**
  1. sync vendors the registry → it now names the engine nobody ships;
  2. a lenient validate (`--allow-new-engines`, sync job only) NAMES it and continues instead of
     failing, because a store that cannot land also cannot spawn the issue that resolves it;
  3. the spawn step opens one tracking issue per new engine, unconditionally (an `always()` step) —
     it runs even when the strict gate is red, since that red IS the condition it explains;
  4. a human/agent PR adds the skill (no bot writes skill content);
  5. `generate-engine-params` writes params + one Dockerfile per engine × arch, committed;
  6. the image matrix picks it up from the params file alone — no workflow edit.
- **The strict gate is the one in the always-running CI unit stage, never the sync job.** The sync
  job tolerates a new engine so the data lands; the unit stage refuses it (`check-engine-skill-gap`)
  until the engine ships a skill or gets a dated, reasoned decision in the unsupported list. If both
  jobs were strict the sync would deadlock; if both were lenient the engine would vanish silently.
- **Freshness is gated separately from presence:** after the skill exists, `check-engine-params`
  fails any PR whose committed params/binaries/Dockerfiles differ from what the skill generates, and
  a report file listing per-engine status is itself checked for staleness. A green local `generate`
  that was never committed is the common miss.

## Keeping engine pins synced to upstream (daily bump)

When engines are pinned to upstream commits in per-engine definitions and the
pins go stale, automate the bump — but keep it deterministic and safe. The full
flow, extractor table, and make targets are in
`references/engine-pin-bump.md`. The rules that matter:

- **Plan with `git ls-remote` only** (branch head, or highest stable same-shape
  tag with its peeled sha). Never move a pin backwards; a failing lookup is
  reported and the other engines continue. A PR exists ⟺ the plan found ≥1 new
  hash.
- **Derive build params from the upstream tree at the new sha with plain code**
  (`git show <sha>:<path>` on a `--filter=blob:none` clone, regex, file parsing)
  — no LLM. Same input → same bytes. Each engine declares which extractors apply
  in a `derive:` front-matter key so the generic code has no per-engine `if`.
- **Apply the derived params into the skill — deriving alone is not enough.**
  Write the `auto` findings (renames, mirrored recipe flags, toolchain, GPU-targets
  var, torch backend) into the skill's front matter so the regenerated params that
  `make build-engine` reads actually carry the new args. Create a `cmake_flags:`
  block when the skill had none (empty arg list) instead of silently skipping.
- **The safety gate is the point:** if the upstream diff touches build-sensitive
  files, don't silently guess. Auto-apply renames and known moves; a REMOVED build
  option or launch flag is a **recorded hard-fail, not fatal** — the pin still
  moves and the PR still opens, with the hard-fail flagged in the PR body so a
  human fixes the skill (CI goes red on the build). Never abort the bump and skip
  the PR on a hard-fail.
- **CI builds only the changed engines.** On a PR, scope the engine-image matrix
  to engines whose params differ from the base branch (`CHANGED=origin/main`); a
  push to `main` keeps the full matrix.
- **A PR-scoped matrix never exercises the whole pinned set — add a dispatchable
  sweep.** Build every engine × backend in parallel from the SAME committed
  params (`workflow_dispatch`, guard job, `matrix` from a make target that reads
  the params, `max-parallel` high), and give the local make target the same four
  scopes from one list: all engines × all backends, one backend, one engine (all
  its backends), one engine × one backend. Each row must carry its OWN
  parameters, resolved from that engine's entry for that backend — never a flag
  string shared across engines. Publish only when the dispatch asks to, and keep
  the PR gate where it is: dropping the changed-images build from the main
  pipeline lets an unbuildable bump merge.
- **A pin edit is surgical:** only `pinned`/`ref`/`version`/`verified`/digest
  change; every other byte is identical (lock with a file-diff test).
- **Regen guard:** after a bump, `generate-engine-params` must change only the
  bumped engine's params/dockerfiles; a change to another engine's file fails.
- **Gate the workflow to collaborators/owner/bot** so a fork/contributor push
  can't drive the upstream's rebuild/PR.
- **Run the registry sync and the engine bump on SEPARATE crons** (two workflows,
  own schedules) so they never block each other.
- **Pin the Python version on host and runner** — use the repo's pinned
  interpreter (`$(PY)`, the venv python) not bare `python3`, and
  `actions/setup-python` the same version in the workflow.

## Converting a prebuilt variant to a source build

`prebuilt: true` is only half of it: an engine's install recipe may download a
release archive or a wheel, so a flag flip still ships an upstream binary — and a
recipe nothing ever ran is usually broken (a `;` inside a flags string cuts the
rendered shell command, exit 127). Full checklist — what to replace in the
recipe, the shared-base/runtime-copy shape, how to prove each backend built the
PINNED sha (not just that an image exists), and how to scope by build cost:
`references/source-conversions.md`.

## Pitfalls

- **The `patch` tool corrupts multi-line Python/YAML block edits.** Replacing a
  multi-line block (a function body, a YAML mapping, a workflow job) repeatedly
  mangled indentation and introduced typos (`arg:g:`, `captureture_output`,
  `$GITHUBUB_OUTPUT`). The reliable fix: do the edit with a Python heredoc that
  does an exact `str.replace` (assert the old block is present first), or rewrite
  the whole file with `write_file` after reading it fully. Verify with
  `python3 -c "import ast; ast.parse(open(f).read())"` / a YAML load after.
- **A strict YAML front-matter parser rejects inline flow mappings and unquoted
  `{`-leading strings** — `{file: x, arg: y}` and `{binary} …` fail with
  "unsupported YAML construct". Use block style and quote strings that start
  with `{`.
- **`^`-anchored regexes need `re.MULTILINE` for `finditer`.** Without it `^`
  only matches at string start, so a scan over a multi-line file returns nothing
  even though the pattern matches a line — silently emptying a "which options
  exist" pass.
- **A removed-option check must compare old vs new, not "not present now".**
  Standard CMake built-ins like `CMAKE_CUDA_ARCHITECTURES` are never `option()`s,
  so "flag not in current options" false-positives on them. Only hard-fail when
  the flag WAS an option at the old sha and is gone at the new sha.
- **A test pin of all zeros parses as int 0 in a strict YAML parser** — `'0'*40`
  becomes `0`, and `old_sha[:8]` then fails with "int not subscriptable". Use a
  hex pin with letters (`'a'*40`).

- **`pkill -f "<pattern>"` can kill the shell running the command itself** —
  the pattern appears in that shell's own command line, so it matches and
  SIGTERMs your session (exit 143/-15). `pgrep -f` first to see what actually
  matches, or use a pattern that cannot appear in the invoking shell's argv.
- **A model file sized to the VRAM budget leaves no room for the KV cache.**
  Picking the largest quant that fits e.g. 85% of the card fills the weights
  and leaves almost nothing for context. When auto-picking a quant for a card,
  leave headroom for the context cache, not just fit the weights.
- **Ambiguous local model names must resolve by path, not bare filename.** When
  the same `.gguf` filename exists in two directories, an error that lists only
  the basenames is useless — show each file's path and accept a full path (or
  a path substring) to disambiguate.
- **Read the fork's build files, not the upstream's.** Forks rename flags and
  add options (e.g. `--spec-draft-adaptive`); the current llama.cpp family
  standard is the `GGML_*` names (`GGML_CUDA`, `GGML_METAL`, `GGML_HIP`) over
  the legacy `LLAMA_CUBLAS`/`LLAMA_HIPBLAS`. Grep the CMakeLists/README of the
  exact repo+branch you build.
- **`git ls-remote` gives you the HEAD/ref to track; verify existence before
  trusting a repo in a newer ecosystem** — not every listed engine exists at the
  URL the registry claims.
- **A `--version`/`--help` check that runs the real binary fails on a GPU-less
  CI runner when the binary probes the device on startup** (vLLM, TensorRT-LLM,
  SGLang, MLX-on-CUDA): the import needs the driver, so every flag exits 1 with
  `ImportError: libcuda.so.1`. Reading the version from the package metadata
  (`importlib.metadata`) proves the WHEELS ARE INSTALLED — not that the binary
  runs — so treat it as a weaker verdict, never as the whole check: keep the flag
  requirement for every cell that can answer on the runner, and let only cells on
  a NAMED, reasoned exemption list lean on the metadata (say so in the report, and
  count them separately). A blanket "policy says device, so pass" is how four
  engine rows went green having proved nothing.
- **Package metadata and the package's own `__version__` disagree.** `sglang.__version__`
  answers `0.0.0` in a ROCm wheel while `importlib.metadata.version("sglang")` is the
  real version — read the distribution's metadata, not the module attribute, and
  refuse `0.0.0` as a version.
- **A CLI can print a log line BEFORE its version.** A fork's `--version` may emit
  `0.00.000.331 I srv  llama_server: initializing ...` and then `version: 0.5.0-dev
  (build …)` with exit 0. Before declaring a flag useless and swapping in a package
  read (or dropping it from the documented flags), run the PUBLISHED image and read
  every line; if the version is there, fix the `detect`/parse to select it. A
  version check must match a version shape (semver, or `pin <sha7+>`), never merely
  "output contains digits" — a timestamped log line satisfies `\d+\.\d+`.
- **A shared `rocm/dev-ubuntu-24.04:7.0-complete` base has no `hip` CMake
  package** — source builds `find_package(hip)` fails. Build ROCm engines on a
  base that ships HIP dev files (e.g. `rocm/pytorch:rocm7.2.4_...
pytorch_release_2.10.0@sha256:4449f856...`), the same one the other ROCm
  engines use.
- **A Hub download must pass the SAME RAM budget and engine that built the
  plan** — the download function defaults to a different (smaller) budget and
  to no engine, so it silently plans a DIFFERENT file than the one the picker
  just showed the user. This bit in production: the picker listed the
  engine-specific plan (Strata → UD-IQ4_XS) but the download call omitted
  `engine=`, recomputed a generic plan, and fetched a quant the engine
  refuses. Reuse the plan already shown to the user instead of recomputing it,
  and assert the download matches the displayed plan. In a unit test, run
  against an EMPTY models dir (`LLAMA_MODELS_ROOT`/`ftmp_path`) so a model
  already on disk (a `download` that returns the local file) does not make the
  chunk fetch 404.
- **An engine that only serves sharded models is not a bug — a single-file
  download for it is.** Strata (Niko1221/Strata) accepts only the quants in its
  own `setup.py` `MODELS` dict, and every one is split into 2–4 GGUF shards
  (ISTA-DASLab GSQ-RCO = 2, Unsloth UD-IQ4_XS = 3, UD-Q4_K_XL = 4); none is a
  single file. A quant that merely CONTAINS a supported token (e.g. `UD-IQ1_M`
  contains `IQ1_M`) is still refused — match the exact quant token, and verify
  the planned files against the engine's own file list before downloading
  tens of GB. When a user asks "why so many files", the answer is the engine's
  shard layout, not a download bug.
- **An engine that serves an HTTP API must never silently lose its container
  image.** A `container: false` because its installer is interactive, or an
  omitted `container:` key, drops it from every ranking list that only counts
  engines with an image. Enforce the rule: the validator must treat an omitted
  `container:` key as "use the default", fail any servable engine with no
  generated image, and a unit test must pin the best engine for EVERY README
  row (happy = vendored copy passes, unhappy = a modified copy with a row
  dropped / order swapped / engine renamed is rejected). Presence in the skill
  tree is not proof of an image: a `servable: true` skill with no container
  backend block emits no Dockerfile and no params entry, so it simply never
  enters the build matrix — and unless the validator is explicit about it, no
  gate reds. After adding such a skill, assert a Dockerfile was actually
  generated for each of its backends, not just that the skill validates.
- **PyYAML may not be on the host python** that the build path runs. Parse the
  engine definition with tools you know the host has, or install the venv
  (which pins pyyaml) before the build step that reads it.
- **The engine container image tag is derived from the start parameters, so
  changing them changes the tag — and the new image only exists once CI has
  published it.** When you edit an engine's `pre_launch`/start step, the launcher
  resolves a NEW image tag that is not yet on the local host or the registry.
  A local `make install` + interactive test then fails at the first engine start
  with a pull error, not because the code is wrong but because the image for the
  new tag has not been built/pushed yet. Before telling the user "you can test
  it now", check whether the new tag is published: `docker images` for the tag
  locally, and the CI `engine-image-<engine>-<backend>` job status. If it is
  still running, say the first start will pull the image only once that job
  finishes (or point the registry at the fork's published image).
- Preflight which CUDA/ROCm toolkit version a build expects rather than
  assuming the newest is what the engine wants.
- **A templated launch line must not contain literal curly braces.** When the
  start command is rendered from a template (`{src}`, `{alias}`, `{port}`, …),
  a Python set/dict literal in the generated command (`c["aliases"] = set(...)
  | {a}`) collides with the template renderer and fails with an unresolved-
  placeholder error. Write the idempotent update with list append / if-not-in
  instead of a set literal.
- **A test that only runs the engine's version check never exercises the start
  command.** A GPU-less CI runner can pass a `--version` check while the real
  launch line dies on an argument the server does not accept. Add a test that
  runs the image's OWN start command against the engine's real server (the
  engine's mock backend stands in for the GPU engine; argument parsing, config
  and the HTTP API are still the engine's real code), asserts the server
  starts, `/v1/models` lists the alias, and a chat to that alias answers as it.
  Confirm it fails on the old launch line (stash the fix, run on main) before
  it passes on the new one.

## References

- `references/hardware-parameter-mapping.md` — per-backend probe→parameter
  mapping table (CUDA/ROCm/Metal/CPU) and the per-engine SKILL.md front-matter
  shape the install runner consumes.
- `references/engine-pin-bump.md` — the daily engine pin-bump flow: plan
  (git ls-remote), surgical pin edit, deterministic E1–E9 param derivation (no
  LLM), regen guard, PR/CI scoping, and the hard-fail safety gate.
- `references/source-conversions.md` — converting a prebuilt engine variant to a
  source build: the install recipe that actually downloads an artifact, the
  never-run compile recipe that breaks on first use, the shared-base/runtime-copy
  image shape, per-backend proof against the pinned sha, and cost-scoped
  exceptions.
