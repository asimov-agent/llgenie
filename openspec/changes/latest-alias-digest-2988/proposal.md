# Gate the engine-level :latest alias digest alongside :<variant> (issue #2988)

## Why

Issue #638 gives each engine exactly ONE canonical variant cell that also carries `:latest` (`engine_image.engine_latest_variant`: `cpu` when the engine declares it, else the first sorted params variant; `publish_refs` appends `:latest` only for that cell). The alias-digest gate landed under issue #2987 (#2990) compares only each cell's `:<variant>` alias with its committed pin tag. A partial or interrupted moving publish — the sweep moved `:<variant>` but `:latest` stayed on an older build, or a canonical-cell publish died after the arch push — leaves `:latest` lagging with every gate green. `:latest` is exactly the tag convenience pulls and fresh installs follow, so a stale `:latest` runs a build `main` does not pin, invisibly (the same green-with-stale class #2987 measured for `edge0:cuda`, `vllm:cuda`, `vllm:rocm`).

## What Changes

- `scripts/check_engine_pins_published.py::_probe`'s existing `alias_check` block gains the engine-level check: for each resolved cell whose variant IS the engine's canonical variant (decided by the SAME `ei.engine_latest_variant` publish uses, so ownership can never disagree between publisher and gate), also resolve `<repo>:latest`. Aligned prints `[pins] LATEST OK <latest-ref>`; a lagging or absent `:latest` prints `[pins] ALIAS LAG <latest-ref> (<latest digest> != <pin digest> | absent) behind committed <ref>` plus the same `[select] <engine> <variant> <tag-suffix>` dispatch-contract line and reds the check (the cell the select names is the canonical cell — the one sweep publishes `:latest` under). Non-canonical cells add no probe: one `:latest` probe per engine, never per variant.
- The knob stays the single `ENGINE_PINS_ALIAS` (no new env): the engine-level check turns on wherever the variant-alias check is on (only registry-liveness sets it; PR lanes and `ci-hf-live` keep tag-existence semantics, unchanged).
- `registry-liveness.yml` needs no edit: its knobbed gate now reports latest lag through the existing `[select]` → #2579 coalesced `push=true` dispatch, and `engine_image.push`'s moving leg already pushes `:latest` for the canonical cell.
- Fixture tests (hermetic, injected digest probes, layered on the #2987 cases): canonical-cell latest aligned → green with `LATEST OK`; latest lag → red with `ALIAS LAG` + `[select]`; latest absent → same red; non-canonical variant cell → NO `:latest` probe for it (one probe per engine); multi-variant engine → the canonical (`cpu`-preferring) cell owns the check.

## Impact

- `scripts/check_engine_pins_published.py` — `_probe` alias block (canonical-variant ownership + `:latest` digest compare), `_probe` final summary line. No new knob, no workflow edit.
- Builds directly on the seam landed by #2990 (the `alias_check` parameter and its loop); this change only extends it.
- `tests/test_check_engine_pins_published.py` — new hermetic cases in place.
- Repair needs no new machinery: a latest-lagged cell selects the canonical cell; the moving sweep already republishes `:<variant>` and `:latest` for it.
- Refs: issue #2988 (this issue, the `Not covered` item split from parent #2987), parent issues #2987/#2990, #638 (`:latest` ownership), #178 (move-and-retest contract).
