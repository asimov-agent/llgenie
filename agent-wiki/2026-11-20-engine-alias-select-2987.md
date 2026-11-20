# Engine alias digest gate: lag selects the moving push (#2987)

Issue: #2987. OpenSpec change: `engine-alias-select-2987`. Branch: `feat/engine-alias-select-2987`.

## What was verified against the spec
- The #178 invariant ("publish the unique tag on the PR; move the arch tag and retest on main") had no detector for its second leg: `make check-engine-pins-published ALL=1` only probes committed pin-tag *existence*, so registry-liveness run `44819931738` was GREEN on `a4afb185e` while three `:<variant>` arch aliases served older builds (`edge0:cuda`, `vllm:cuda`, `vllm:rocm` — digests in the issue Technical section).
- Spec (ADDED requirement, `specs/engine-alias-realignment/spec.md`): with the opt-in `ENGINE_PINS_ALIAS` knob on, the committed-scope probe resolves each enabled cell's `:<variant>` alias manifest, compares digests against the committed pin tag, and on lag prints `[pins] ALIAS LAG <ref>` + the unchanged `[select] <engine> <variant> <tag-suffix>` contract (#2561/#2567) and exits 1; with the knob off, behavior is bit-identical to before.
- Implementation in `scripts/check_engine_pins_published.py` (`_probe`/`check_committed` seams, `ENGINE_PINS_PATIENCE_SECONDS` knob precedent #2973); knob set ONLY in `.github/workflows/registry-liveness.yml` (both `ALL=1` gate steps, `ENGINE_PINS_ALIAS: "1"`). The liveness gate step already tolerates a red sweep (`set +e`) and dispatches the `[select]` lines through the #2579 coalesced `push=true` engine-build sweep, whose moving leg republishes the committed tag and moves `:<arch>`/`:latest`.
- Tests (`tests/test_check_engine_pins_published.py`, updated in place): hermetic injected-digest cases (aligned stays green; lag prints ALIAS LAG + `[select]` and reds; missing alias reds; malformed knob value is loud), a knob-unset case pinning tag-existence-only semantics, and a wiring test pinning the knob to exactly the two liveness `ALL=1` steps.
- Live proof at head `e600c9c6d`: `ENGINE_PINS_ALIAS=1 make check-engine-pins-published ALL=1` → 29 cells checked, 26 `ALIAS OK`, 3 `ALIAS LAG` (exactly the measured stale aliases), 3 `[select]` lines, gate rc=1 (make rc=2). Detection red is the green outcome; the post-merge realignment is main-side landing work tracked by #2989.

## Key decisions
- Opt-in env knob instead of always-on: PR lanes and `ci-hf-live` sit inside normal merge windows where an alias is legitimately between merges; only the liveness invocation (the one whose contract is "repair on main") turns the comparison on.
- Reuse the existing `[select]` → coalesced `push=true` dispatch unchanged — the repair machinery from #2561/#2567/#2579 already moves moving tags on the push leg; no new dispatch path.
- `:latest` alias lag detection explicitly out of scope, filed as its own issue (#2988); post-merge realignment proof filed as #2989.

## Current status
X1 `e600c9c6d` (gate + workflow + tests + OpenSpec change); proofs at that head: `make openspec-validate` rc=0, `make check-workflows` rc=0, live detection sweep as above, `make test-unit` rc pending at ship time. Ship: PR with `closes #2987`, `Not covered` naming #2988/#2989; issue/PR/commit AC mirrors ticked with replayable proven clauses.
