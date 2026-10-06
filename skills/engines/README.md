# Engine skills

One agent skill per inference server in the
[trending-local-llms](https://github.com/andyholst/trending-local-llms) `engines{}`
registry (issue #98). `SKILL.md` is the **single source of truth** for how to detect,
install and launch that engine on each kind of hardware. `scripts/engine_skills.py`
is the generic runner. It has no engine-specific code, so agents and llgenie
run the same steps.

```
make engine-hardware                     # what was detected (compute cap, CUDA arch, gfx, CUDA major, ...)
make engine-list                         # every skill, servable mode, backends, which fit this machine
make engine-plan ENGINE=vllm             # the exact steps/flags rendered for this machine
make engine-check ENGINE=tensorfold      # blockers (backend, OS, compute cap, CUDA, gfx, prereqs)
make generate-engine-params             # skills -> containers/engines/params/<id>.json (frozen per arch)
make build-engine ENGINE=ollama          # build its image from the frozen params (this machine's arch)
make run-engine ENGINE=ollama MODEL=...  # serve http://127.0.0.1:11434/v1 as llm-local
make engine-install ENGINE=mlx BACKEND=metal   # Metal only: native `uv tool install`
make skills-validate                     # all skills vs the registry (CI gate)
```

`BACKEND=<cuda|rocm|vulkan|metal|cpu>` overrides the detected backend for
plan/check/install/detect.

Container images do **not** read skills. `make generate-engine-params` freezes each
skill into `containers/engines/params/<id>.json` (one variant per backend x GPU arch).
`make build-engine ENGINE=<id> [ARCH=cuda-sm89]` builds only from that file. After
editing a skill, run `make generate-engine-params` and commit the diff. CI's
`make check-engine-params` fails if you forget.

## Where engines go

- llama.cpp forks: `$SERVER_ROOT/<tree>` (default `~/repository/git`), build dir `build-<backend>`.
  This is the same place `make install` / `make build-variant` already use.
- Everything else: **inside the engine's container image** (`/opt/llgenie/...`), built by
  `make build-engine`. Python engines use `uv pip install --system` into the image's Python;
  the container is the isolation. No venvs.
- Metal (macOS, no containers): `uv tool install` on the host.
- Never `sudo`, never `curl … | sh`. Release archives are checksum-verified before extraction.

## Format

YAML front matter (a strict subset, parsed with the stdlib and checked against
PyYAML in tests; quote dates and strings containing `:` or `#`), then a markdown body
for humans.

| Key | Meaning |
|---|---|
| `name` | `engine-<id>` (dots become dashes) |
| `description` | `Use when …` trigger line |
| `engine` | exact key in the registry `engines{}` |
| `id` | directory name |
| `repo`, `ref`, `ref_kind` | upstream repo and the branch or tag tracked |
| `version` | release version for tag-tracked engines (`{version}` in steps) |
| `pinned` | 40-hex commit last verified. Drift sync (#100) bumps it |
| `verified` | date it was verified (quoted) |
| `servable` | `true` (OpenAI HTTP server), `false` (never installed), `via` (served by the engines in `via:`) |
| `backends`, `os` | `cuda` `rocm` `vulkan` `metal` `cpu`; `linux` `darwin` |
| `formats`, `quants` | what it loads (`gguf`, `safetensors`, `mlx-safetensors`, `exl3`, …), and the GGUF quant types |
| `requires` | hardware floors: `min_compute_cap.<backend>`, `min_cuda.<backend>`, `gpu_targets.<backend>` allow-list |
| `prereqs` | tools that must be on PATH, `common` + per backend |
| `src_dir`, `build_dir` | clone/build locations (defaults `{prefix}/src`, `{src}/build-{backend}`) |
| `cmake_flags` | `common` + per-backend base flags |
| `hw_flags` | per backend `<hw param>: "<flag template>"`, emitted only when that parameter was detected |
| `env` | `common` + per-backend env for install and launch |
| `install` | `common` + per-backend shell steps; `use:<id>` installs another skill first |
| `binary`, `detect` | path to the server, and the command that succeeds iff it is installed |
| `pre_launch`, `launch`, `post_launch` | launch template; must bind `{host}:{port}` and expose `{alias}` |
| `health` | readiness probe |
| `alias_mode` | how `llm-local` is exposed: `flag`, `create` (ollama create / litert import), `config` (alias in a config file), `symlink` (served id = dir name) |
| `upstream_watch` | upstream files whose change can invalidate the skill (drift sync diffs them) |
| `container` | `false` (no image, e.g. Strata's interactive installer) or per backend `{base, apt, cuda_archs, gpu_targets}` overrides for `make generate-engine-params` |

### Placeholders

From hardware detection: `{os}` `{arch}` (amd64/arm64) `{machine}` (x86_64/aarch64)
`{backend}` `{compute_cap}` `{cuda_arch}` `{cuda_version}` `{cuda_major}` `{gpu_targets}`
`{jobs}`. From the skill or runner: `{id}` `{repo}` `{ref}` `{pinned}` `{version}` `{prefix}`
`{src}` `{build}` `{binary}` `{server_root}` `{cmake_flags}` `{host}`
(127.0.0.1) `{port}` (11434) `{alias}` (llm-local). Left for the launcher: `{model}`
`{drafter}`.

### Hardware parameters

| Parameter | Source | CI seam |
|---|---|---|
| `compute_cap`, `cuda_arch` | `nvidia-smi --query-gpu=compute_cap` (8.9 -> 89) | `LLGENIE_CUDA_ARCH` |
| `cuda_version`, `cuda_major` | `nvcc --version` | `LLGENIE_CUDA_VERSION` |
| `gpu_targets` | `rocminfo` GPU agents (`gfx1100`) | `LLGENIE_GPU_TARGETS` |
| `backend` | `detect_server.detect_backend()` (+ rocm when hipconfig + gfx) | `LLAMA_BACKEND` |
| card RAM | `detect_server.detect_card_ram_bytes()` | `LLAMA_RAM_BYTES` |
| `jobs` | CPU count | `BUILD_JOBS` |

## Adding an engine

1. Read the engine's README and build docs at a tag or commit, and record the sha in `pinned`.
2. Create `skills/engines/<id>/SKILL.md` with the keys above. Derive every
   hardware-dependent flag from a detected parameter (`hw_flags`, `{cuda_major}`, …).
   Never hard-code one GPU.
3. `make skills-validate && make generate-engine-params && make build-engine ENGINE=<id>`, then let CI build the image matrix.
4. Commit through a feature branch and PR. `make test-unit` checks the parser,
   the endpoint contract and isolation for every skill.
