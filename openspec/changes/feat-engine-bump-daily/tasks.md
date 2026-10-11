# feat-engine-bump-daily — Tasks

Checklist of record. Each step maps to a spec requirement in
`openspec/changes/feat-engine-bump-daily/specs/engine-bump-daily/spec.md`.
Ticked the moment the work is verified with real tool output.

## Plan (scripts/engine_bump.py)

- [x] 1.1 `plan([engine])`: per skill, `git ls-remote` the branch head or the
      highest stable same-shape tag (peeled sha); skip when ≤ current pin;
      `lookup failed` after 3 tries with backoff, others continue; output the
      sorted `[{id, repo, ref_kind, old_ref, old_sha, new_ref, new_sha}]` list.
- [x] 1.2 Tag shape regex derived from the current tag; pre-releases dropped;
      numeric sort; never moves backwards.

## Pin (scripts/engine_bump.py)

- [x] 1.3 `pin(skill, new_ref, new_sha)`: targeted frontmatter edit of only
      `pinned`/`ref`/`version`/`verified` (+ image digests); every other byte
      identical (file diff test).

## Derive (scripts/engine_params_derive.py)

- [x] 2.1 `derive(skill, sha)`: `--filter=blob:none` clone + `git show
      <sha>:<path>`; stable `findings` JSON; byte-deterministic for a fixed sha.
- [x] 2.2 E1 cmake options (option/set CACHE) + E2 rename
      (`llama_option_depr`) auto-applied.
- [x] 2.3 E3 removed option → recorded hard-fail; pin still moves, PR still opens
      (body flags it), CI goes red on the build.
- [x] 2.4 E4 upstream recipe flags (mirror auto, non-mirror report-only).
- [x] 2.5 E5 toolchain ARG bump → base image follows.
- [x] 2.6 E6 GPU targets var rename.
- [x] 2.7 E7 python/torch pin update.
- [x] 2.8 E8 removed launch flag → recorded hard-fail; pin still moves, PR still
      opens (body flags it), CI goes red on the build.
- [x] 2.9 E9 per-backend watch diff (report-only, `upstream_watch_backends`
      override).
- [x] 2.10 Unparseable extractor input → recorded hard-fail with path + grep
      output; pin still moves, PR still opens (body flags it).

## Apply + regen

- [x] 3.1 `bump(engine)`: pin + derive + apply + `make generate-engine-params`;
      regen guard isolates the engine (a change to another engine's params
      fails the job).

## Make targets

- [x] 3.2 `engine-bump-plan`, `engine-derive`, `engine-bump`,
      `engine-bump-daily [DRY=1]` wired into the Makefile + help.

## CI

- [x] 4.1 `engine-bump.yml` (separate from `registry-sync.yml`): `plan` +
      `bump` matrix, weekly cron `23 6 * * 1` (Monday) + `workflow_dispatch`,
      guard (collaborators/owner/bot only), per-engine `chore/engine-bump-<id>`
      PR (one squashed commit, never merged), hard-fail flagged in the PR body.
      `registry-sync.yml` keeps its own daily cron `17 5 * * *` — the two run
      at different times, independently.
- [x] 4.2 `ci.yml` `changed-engines` step on `pull_request`:
      `make list-engine-images CHANGED=origin/main` scopes the engine-image /
      engine-published-test matrices; pushes to `main` keep the full matrix.

## Tests (tests/test_engine_bump.py)

- [x] 5.1 plan: branch head, tag highest-stable-same-shape, never backwards,
      lookup-failure-continues.
- [x] 5.2 pin edit surgical (file diff).
- [x] 5.3 derive deterministic.
- [x] 5.4 E2 rename auto-applied.
- [x] 5.5 E3 removed option hard-fails.
- [x] 5.6 E4 recipe flag mirrored.
- [x] 5.7 E5 toolchain bump.
- [x] 5.8 E6 gpu targets var renamed.
- [x] 5.9 E7 torch backend updated.
- [x] 5.10 E8 removed launch flag hard-fails.
- [x] 5.11 E9 watch diff maps backends.
- [x] 5.12 unparseable recipe hard-fails.
- [x] 5.13 regen guard isolates engine.
- [x] 5.14 changed-engines scopes matrix on PR; full on main.
- [x] 5.15 bump-daily DRY=1 no push.
- [x] 5.16 apply writes derived params into the skill (rename, mirror, toolchain,
      gpu-targets var); a hard-fail applies nothing.
- [x] 5.17 full bump happy path: empty arg list -> new args land in the params
      JSON `make build-engine` reads, for every arch the engine supports.
- [x] 5.18 real docker build: `make build-engine ENGINE=llama.cpp ARCH=cpu` builds
      the image and its entrypoint reports a version (docker required).

## Docs + gate

- [x] 6.1 README section "Daily sync: registry + engine pins".
- [x] 6.2 `make test-unit` green; `make openspec-validate
      NAME=feat-engine-bump-daily` passes; `make loop` green.
- [x] 6.3 Issue #107 body updated to match this change; commit + push branch;
      open PR against upstream main referencing #107.
