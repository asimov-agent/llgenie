# Engine builds: verify by executing, and source vs prebuilt

## The rule

An engine change is not verified until an image has been **built and its binary run**. Reading the
skill, the params or the workflow proves nothing: the params can be structurally valid and still
produce a shell line that fails, and the CI claim "this PR builds the engine" may be filtered to
only the images the PR changed (`ci.yml engine-matrix` uses `CHANGED=<base>`).

## The one chain, in order

```bash
make generate-engine-params ENGINE=<id>        # skill -> params/<id>.json + dockerfiles/<id>/Dockerfile.<arch>
make check-engine-params                       # committed params == what the skill generates
make build-engine ENGINE=<id> ARCH=<cpu|cuda|rocm|vulkan>
make test-engine-image ENGINE=<id> ARCH=<arch> # version + the flags a user types, run in the image
```

Quote the real output. What makes it proof: `--version` reporting the **pinned sha/commit** (e.g.
`0.7.0-dev (build 11870, commit 74bca3950)` for pin `74bca395…`) — that is the only cheap signal
that the image was built from the commit the params name, not inherited from an upstream image.

## Source vs prebuilt — audit first

A variant with `prebuilt: true` starts `FROM` an upstream image and its `install` steps only add the
entrypoint, so the derived parameters are metadata: nothing compiles, and a broken compile recipe
stays hidden. Audit before claiming anything:

```bash
python3 - <<'EOF'
import json, glob
for f in sorted(glob.glob("containers/engines/params/*.json")):
    d = json.load(open(f))
    for k, v in d["variants"].items():
        print(f"{d['id']:<28}{k:<7} prebuilt={v.get('prebuilt')} steps={len(v.get('install') or [])}")
EOF
```

To convert a variant to a source build, the skill's `install:` block usually already compiles (the
`container:` block is what pointed at the official image). Replace it with the compile form and
regenerate:

```yaml
container:
  cuda:
    runtime: true
    runtime_copy: ["{build}/bin"]
  cpu:
    runtime: true
    runtime_copy: ["{build}/bin"]
```

## Pitfall: `;` inside a skill's cmake flags

`cmake_flags` are joined with spaces and interpolated into ONE shell step (`{cmake_flags}` in the
install step). A `;` inside the value therefore terminates the command: the flags after it run as a
program and the build dies with `bash: -DLLAMA_BUILD_TESTS=OFF: command not found` (exit 127).
Write the flags space-separated, never `;`-separated, and grep for the shape before trusting a
converted skill:

```bash
grep -rn '; -D' skills/engines/*/SKILL.md
```

## Scopes (one list, four questions)

```bash
make build-engines                        # every engine x variant, in parallel (JOBS=, default nproc)
make build-engines ARCH=cuda              # one backend, every engine
make build-engines ENGINE=vllm            # one engine, every arch type
make build-engines ENGINE=vllm ARCH=cuda  # one row
make engine-build-matrix [ENGINE=] [ARCH=]  # the JSON matrix the dispatched sweep consumes
```

`make engine-build-matrix` and the CI matrix both read `scripts/engine_image.py matrix` over
`containers/engines/params/*.json`, so the local command and the dispatched sweep cannot disagree.
Each row carries its own `arch` / `build_args` / `install` for that backend — nothing is shared
between engines or backends.

## Deterministic derive vs the LLM review

`scripts/engine_params_derive.py` writes the params ("No LLM anywhere: git, regex and file parsing
only"). The `engine-params-review` Hermes leg runs after it and may only PROPOSE a flag whose flag
AND verbatim quote appear in the named upstream file — the host drops anything else, then regenerates.
When a proposal is dropped, name the dropped flag and the reason rather than arguing the review
worked.

## Worktree caveat

`make build-engine` on the host is fine from a worktree, but the containerized test stages are not
unless the parent `.git` is mounted: a worktree's `.git` is a FILE pointing at
`<main-repo>/.git/worktrees/<name>`, so a container holding only the worktree answers
`fatal: not a git repository` (git-dependent tests then exit 128). `make test-unit` already passes
`WORKTREE_MOUNT`; a hand-run `docker run … pytest` must add
`-v <main>/.git:<main>/.git:rw`.
