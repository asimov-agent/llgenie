# Engine pin bump (daily sync to upstream latest)

When engines are pinned to upstream commits in per-engine definitions and the
pins go stale, automate the bump. Keep it deterministic and safe — the whole
point is that a stale pin silently ships a suboptimal build, and a blind bump
silently ships a broken one.

## The flow

1. **Plan** — `git ls-remote` only, per engine:
   - `ref_kind: branch` → `git ls-remote <repo> refs/heads/<ref>`; new pin = head sha.
   - `ref_kind: tag` → `git ls-remote --tags --refs`, keep tags of the SAME SHAPE
     as the current tag (derive a regex from it), drop pre-releases
     (`rc|alpha|beta|dev|pre|post`), sort numerically, take the highest; new pin =
     peeled sha (`<tag>^{}`).
   - Never move backwards (highest ≤ current → skip). Same sha → skip.
   - A failing lookup → 3 tries with backoff, then `lookup failed`; other engines continue.
   - Output: `[{id, repo, ref_kind, old_ref, old_sha, new_ref, new_sha}]` sorted by id.
   - **A PR exists ⟺ the plan found ≥1 new hash.** This is the invariant the
     workflow's matrix job keys on.

2. **Pin** — surgical front-matter edit: only `pinned`/`ref`/`version`/`verified`
   (and image digests) change; every other byte of the definition is identical.
   Lock with a file-diff test.

3. **Derive** — read the upstream tree at the new sha with plain code (no LLM):
   `git show <sha>:<path>` on a `--filter=blob:none` clone (nothing checked out),
   regex + file parsing. Same input → same bytes. Each engine declares which
   extractors apply in a `derive:` front-matter key so the generic code has no
   per-engine `if`.

4. **Apply** — write the derived `auto` findings into the skill's front matter
   (renames, mirrored recipe flags, toolchain, GPU-targets var, torch backend) so
   the regenerated params that `make build-engine` reads actually carry the new
   args. This is the step that makes "new arguments get added to the parameter
   list" real — deriving without applying leaves the params unchanged. When the
   skill has NO `cmake_flags:` block yet (empty arg list), CREATE one (a `common`
   line) instead of silently skipping the mirror. A hard-fail finding is never
   applied (nothing is guessed).

5. **Regen guard** — after the bump, `generate-engine-params` must change ONLY the
   bumped engine's `params/<id>.json` and `dockerfiles/<id>/*`; a change to
   another engine's file fails the job.

6. **PR + CI** — one PR per changed engine (`chore/engine-bump-<id>`, one squashed
   commit, never merged by automation). On `pull_request`, scope the engine-image
   matrix to engines whose params differ from the base branch
   (`CHANGED=origin/main`); a push to `main` keeps the full matrix. A red PR means
   the new commit needs a manual skill fix.

7. **Gate** — the workflow refuses to run unless the actor is a collaborator, the
   repo owner, or the bot (GitHub API collaborators endpoint, 204 → allowed).

**Run the registry sync and the engine bump on SEPARATE crons.** Two independent
workflows (`registry-sync.yml` and `engine-bump.yml`) with their own schedules so
they never block each other — do not combine them into one `daily-sync.yml`.

**Pin the Python version on both host and runner.** The repo pins one Python
(e.g. 3.11); the bump make targets must use the pinned interpreter (`$(PY)`, the
venv python when present) not bare `python3` (which may be a newer host default),
and the workflow's bump job must `actions/setup-python` the same version so host
and CI run the identical interpreter.

## The safety gate (the part that matters)

If the upstream diff between old and new pin touches build-sensitive files, do
NOT silently guess:

- **Auto-apply** renames and known moves (a `-DOLD` with a declared `NEW`;
  toolchain `ARG` bumps; a renamed GPU-targets variable; a torch `cu128`→`cu130`).
- **Hard-fail is recorded, NOT fatal.** When a build option or launch flag was
  REMOVED, or an extractor cannot parse its file (file moved, recipe has no
  `cmake` line, ARG missing), the pin STILL moves and a PR STILL opens — the
  hard-fail is flagged in the PR body so a human fixes the skill, and CI goes red
  on the build until they do. Nothing is guessed; `main`'s pin is never touched
  directly (the change only lands via the merged PR). Do NOT abort the bump and
  skip the PR on a hard-fail — the user wants the PR opened regardless so the
  problem is visible and fixable on the branch.
- **Report-only** the per-backend watch diff (`upstream_watch` files → which
  backends they affect) and non-mirrored recipe flags.

## Extractor table (deterministic, no LLM)

| # | Extractor | Reads | Rule | Action |
|---|---|---|---|---|
| E1 | cmake options | `option(NAME …)` / `set(NAME … CACHE …)` | set of options at the new sha | input for E2/E3 |
| E2 | cmake renames | `llama_option_depr(LEVEL OLD NEW)` | skill `-DOLD` with a known `NEW` | auto: replace with `-DNEW` (keeps value) |
| E3 | cmake removed | E1 + E2 | a skill `-DNAME` that WAS an option at the old sha and is gone now | hard fail |
| E4 | upstream recipe | `cmake -B/-S …` line(s) in each backend recipe Dockerfile (joined across `\` continuations) | recipe `-D` flags in `mirror` missing/different | auto: add/update; non-mirror report-only |
| E5 | toolchain | `ARG CUDA_VERSION/ROCM_VERSION` | differs from skill `toolchain.<backend>` | auto: update → base image follows |
| E6 | gpu targets var | which of `GPU_TARGETS`/`AMDGPU_TARGETS` the HIP CMakeLists reads | skill uses the other name | auto: rename in `hw_flags` |
| E7 | python/torch | `requires-python`, `torch==…+cu128` | different Python minor / torch CUDA flavour | auto: update `toolchain.python`/`torch_backend` |
| E8 | launch flags | string literals in `flags_from`, or `--help` of the built cpu image | a skill launch flag no longer accepted | hard fail |
| E9 | watch report | `git diff --numstat old..new -- <upstream_watch>` | changed files → backends (`ggml-cuda/`→cuda, `ggml-hip/`→rocm, `ggml-vulkan/`→vulkan, `ggml-metal/`→metal, top-level→all, `arg.cpp`/`server/`→launch) | report-only |

## Make targets

```
make engine-bump-plan [ENGINE=<id>]   # plan (git ls-remote only)
make engine-derive ENGINE=<id> [SHA=] # findings JSON for a sha, no writes
make engine-bump ENGINE=<id>          # pin + derive + apply + regen, no push
make engine-bump-daily [DRY=1]        # what the workflow runs; DRY=1 prints only
```

## Testing

Fixture git repos are REAL git repos created in the test (init/commit/tag), not
mocked subprocess calls — plan/derive run against real git. No network, no skips.

- **Prove the apply step with an empty-arg-list happy path.** Start a fixture
  skill with NO `cmake_flags`, bump from an old commit to a new one whose recipe
  adds flags, and assert the new args land in the regenerated params JSON that
  `make build-engine` reads, for EVERY arch the engine supports. This is the test
  that catches "derive detects but never applies" — the params stay unchanged if
  the apply step is missing.
- **Add a real docker build test** for the lightest engine (e.g. llama.cpp cpu,
  base already pulled) that actually runs `make build-engine` and asserts the
  image's entrypoint reports a version. This proves the generated Dockerfile +
  params build a working image end-to-end, not just that the params are well-formed.
