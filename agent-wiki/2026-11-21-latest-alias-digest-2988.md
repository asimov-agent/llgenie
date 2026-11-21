# Engine `:latest` alias digest gated by the pin check (issue #2988)

Issue: #2988 (split from parent #2987, whose gate landed in PR #2990).
OpenSpec change: `latest-alias-digest-2988`.

## Verified against the spec

- `scripts/check_engine_pins_published.py::_probe`'s `alias_check` block gained the
  engine-level check: `<repo>:latest` is resolved exactly once per engine, from the
  canonical variant cell's iteration only, with ownership decided by the SAME
  `engine_image.engine_latest_variant` (`publish_refs`), so publisher and gate agree
  on who owns `:latest` (issue #638 rule: `cpu` when declared, else first sorted
  params variant).
- Output contract: aligned → `[pins] LATEST OK <ref>`; lag/absent →
  `[pins] ALIAS LAG <ref> (<reason>) behind committed <ref>` + the canonical cell's
  `[select] <engine> <variant> <tag-suffix>` line; red through the existing lag
  summary ("issues #2987/#2988"). No new knob, no workflow edit — the single
  `ENGINE_PINS_ALIAS` gates both aliases; only `registry-liveness.yml` sets it, so
  PR lanes and `ci-hf-live` keep tag-existence semantics.
- Hermetic unit tests (injected digest probes, no network): aligned green; lag-alone
  red with `[select]`; absent `:latest` red; `:latest` probed exactly once per
  engine; `:latest` compared against the CANONICAL digest, not another variant's;
  no-cpu engine (`tensorfold`→`cuda`) owns `:latest` via first sorted variant; knob
  off → zero `:latest` probes.
- Live proof at the change head (`ENGINE_PINS_ALIAS=1 ALL=1 make
  check-engine-pins-published`): 13 engines each carry one `LATEST OK` line; 26
  `ALIAS OK` and 4 `ALIAS LAG` of 29 with `[select]` lines for `edge0 cuda`,
  `vllm cuda`, `vllm rocm` — expected mid-wave lag that the #2579 dispatch repairs.

## Decisions

- Extend the existing `alias_check` knob rather than add a second env: the engine
  `:latest` gap is the same half-moved-publish class #2987 measured for arch
  aliases, and the repair path (`[select]` → moving push republishing `:<variant>`
  and `:latest` for the canonical cell) already exists.
- Ownership read through the publisher's own function, not a re-derived rule — the
  gate and `publish_refs` must never disagree about which variant carries `:latest`.

## Status

Implementation + tests green locally (47/47 in the gate's test file); PR pending
against upstream main from `feat/latest-alias-digest-2988`.
