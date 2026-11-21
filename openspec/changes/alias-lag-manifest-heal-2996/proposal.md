# Heal alias-lagging cells with a manifest move instead of a build dispatch (issue #2996)

## Why

Registry liveness has been red on every run since `14338733e` (runs 44865940908, 44879637744, 44882516581) on the same two committed cells: `vllm:cuda` on `sha256:5ebbd93f…` behind committed `3a4d82f5-4c1f3eee-cuda` (`sha256:b62be545…`), and `vllm:rocm` on `sha256:0e636144…` behind committed `3a4d82f5-d04739cb-rocm` (`sha256:1e74e680…`). The repair premise carried over from #2987/#2989 — a lagging cell emits `[select]` and rides the coalesced `push=true` sweep — is measurably false for these cells: `vllm` is in `DEFAULT_CPU_ONLY` (`scripts/engine_image.py`), so the matrix only ever builds `vllm-cpu`; a sweep completes green (44868119305, 44881159100, 44884434390) and structurally cannot move `vllm:cuda`/`vllm:rocm`; the only single-cell repair shape (`-f engine=vllm -f arch=cuda|rocm`) OOMs (42176975953, exit 143) or wall-cancels (~4 h, 42159549121). Fire-loop: red gate → green-but-useless sweep → identical lag → red gate.

The lag is not a missing image. The exact committed tags RESOLVE in ghcr with exactly the pinned digests; only the variant aliases point elsewhere. The repair is a registry-side manifest move (`docker buildx imagetools create -t <repo>/<engine>:<variant> <repo>/<engine>@<pin-digest>`), GPU-agnostic and runner-cheap — no build at all.

## What Changes

- `scripts/check_engine_pins_published.py` routes the gap by gap class: an alias lag (or absent alias) whose committed pin tag RESOLVES now prints a new contract line `[aliasmove] <engine> <variant> <tag-suffix> <pin-digest>` INSTEAD of `[select]`, because the repair is a tag move, not a build. Manifest-unknown cells keep `[select]` and the #2579 coalesced sweep unchanged. Alias-lag cells no longer reach `engine-build.yml` dispatch at all.
- New `scripts/engine_alias_move.py` (group "CI entrypoints"): moves `:<variant>` to the committed pin digest with `docker buildx imagetools create` (registry-side manifest re-point, no build, no engine execution), verifies after the move by re-resolving the alias digest against the pin digest via `engine_image._digest_http`, and refuses a malformed contract (engine/variant/suffix/digest, digest must be `sha256:<64 hex>`). Prints `[alias-move] MOVED <alias-ref> -> <digest>` or `[alias-move] FAIL …`.
- New make target `engine-alias-move` (mk/engines.mk) wrapping the script with `ENGINE=` / `VARIANT=` / `SUFFIX=` / `DIGEST=`.
- `.github/workflows/registry-liveness.yml` gains a heal step BEFORE the fleet gate: when no same-head publisher is in flight, it runs the knobbed gate once, parses `[aliasmove]` lines (contract-validated), logs into GHCR with the job token (new `packages: write` permission — the engine-build.yml:252 same-repo pattern), and runs `make engine-alias-move` per cell. A healed cell reads ALIAS OK on the fleet gate in the same run; a failed move stays a red gate with named cells. A malformed contract line reddens the step.
- `scripts/package-layers.json`: `engine_alias_move` joins "CI entrypoints" with stated edges to `engine_image` (exact-tag formula + manifest authority) and `proc` (the one subprocess seam).
- Tests: the lag scenarios in `tests/test_check_engine_pins_published.py` now demand `[aliasmove]` (with the pin digest) and no `[select]` for lag cells — including the `vllm`/`cuda` DEFAULT_CPU_ONLY shape, which selects a move and never a `engine=vllm arch=cuda` build dispatch; a new `tests/test_engine_alias_move.py` pins the imagetools command shape, post-move verification, and contract refusal; a workflow test pins the liveness heal step (contract parse, packages permission, gate-before-heal ordering).

## Impact

- `scripts/check_engine_pins_published.py` — lag branch emits `[aliasmove]`; `[select]` stays manifest-unknown-only.
- `scripts/engine_alias_move.py` (new), `mk/engines.mk` (new target), `scripts/package-layers.json` (new module + edges).
- `.github/workflows/registry-liveness.yml` — `packages: write`, heal step before the fleet gate.
- `tests/test_check_engine_pins_published.py` (updated lag tests), `tests/test_engine_alias_move.py` (new).
- `docs/BOTS.md` target table re-rendered (`make bots-targets-index`), agent-wiki entry.
- The three live lag cells are healed by the first registry-liveness run of the merged tip (GitHub event on the merge push — no manual dispatch, no rerun); `make post-merge-live-check` then reads the green run.
- Corrects issue #2989's repair premise (its verification must now watch a manifest move, not a sweep) and links #2988 (`:latest` digest gate) unchanged.
- Not covered (separate issues, already linked): #2997 cancel policy for stalled in_progress jobs; #2988 `:latest` alias digest gate.

Refs: issue #2996 (Problem/Why/fix/AC with measured runs and digests), side issues #2997, #2988, correction target #2989.
