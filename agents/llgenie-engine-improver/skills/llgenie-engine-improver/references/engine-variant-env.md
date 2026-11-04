# Threading a build-time env var into an engine variant (and who owns the params file)

## The params file is generated — the skill is the source of truth

`containers/engines/params/<id>.json` (and `dockerfiles/<id>-<arch>`, `binaries.json`) are emitted from
`skills/engines/<id>/SKILL.md` by `make generate-engine-params`.

- **Never hand-edit the params JSON.** `make check-engine-params` asserts the committed file matches its
  skill and reds with `<N> file(s) stale`; a hand-edit is both a gate red and invisible to the generator,
  so the next regen silently reverts it.
- Edit the skill, then `make generate-engine-params ENGINE=<id>` and `make check-engine-params`
  (must print `0 file(s) stale`). Commit skill + regenerated params in the SAME commit.
- Editing only the generated file is the trap that looks complete locally: the `docker build` you launch
  from it works, then CI rebuilds from the regenerated (unchanged) params and the tweak is gone.

## env: common vs per-backend

`build_env(skill, backend, hw, extra)` merges `env.common` then `env.<backend>` into the variant's `env`
dict (backend key overrides common), and the install runner exports each entry
(`env_prelude` → `export K="V"; `) before EVERY install step.

So a build-time variable reaches the build container's shell by being placed under the skill's `env:`
block — no Dockerfile edit, no `--build-arg`, no wrapper script:

```yaml
env:
  cuda:
    UV_HTTP_TIMEOUT: "120"
  cpu:
    VLLM_CPU_KVCACHE_SPACE: "4"
```

Scope it to the backend that needs it (`env.<backend>`) unless every backend wants it (`env.common`).

Verify the value actually landed in the generated variant:

```bash
python3 -c "import json;print(json.load(open('containers/engines/params/<id>.json'))['variants']['<arch>'].get('env'))"
```

An empty `{}` there means your edit is not where python reads — re-read the SKILL file itself before
concluding the edit failed (a stale local view of the file is the common cause).

## Classifying an install-step failure: transfer flake vs pin defect

An install step that dies mid-download or mid-extract (uv/pip resolving or unpacking large wheels such as
cusparse/cudnn-class) on a 30s default HTTP timeout is a LINK flake, not a bad pin. The remedy is a
variant env timeout (`UV_HTTP_TIMEOUT: "120"`) plus regenerate — do NOT repin the package, edit the apt
set, or add retry loops to the install script to "fix" a transfer timeout.

Distinguish it by WHERE in the step it failed: resolution/satisfiability errors (`no matching
distribution`, `unsatisfiable`) are pin/index defects; timeout/connection-reset/reset-by-peer during a
transfer are link flakes. The two get opposite fixes and a wrong call costs a full rebuild cycle.

## The variant env is NOT free — it feeds the image tag

The engine image tag hashes the variant's params, so adding/changing `env.<backend>` recomputes the tag
and makes CI publish a new image for that cell. Never treat an env tweak as "metadata only": expect a
fresh build, and do not locally-bulit-image a change whose tag CI has not published yet.
