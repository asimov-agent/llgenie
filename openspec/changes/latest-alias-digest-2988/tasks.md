# Tasks — latest-alias-digest-2988

## 1. Extend the gate's alias block

- [x] 1.1 In `scripts/check_engine_pins_published.py::_probe`'s `alias_check` block, decide each engine's canonical variant with `engine_image.engine_latest_variant` (the same function `publish_refs` uses) and probe `<repo>:latest` once per engine, from the canonical cell's iteration only.
- [x] 1.2 Aligned `:latest` prints `[pins] LATEST OK <ref>`; a lagging or absent `:latest` prints `[pins] ALIAS LAG <ref> (<reason>) behind committed <ref>` plus the canonical cell's `[select]` line and reds the check through the existing lag summary.

## 2. Tests (hermetic, injected digest probes)

- [x] 2.1 Canonical-cell `:latest` aligned → exit 0 with a `LATEST OK` line.
- [x] 2.2 `:latest` digest lag → exit 1 with `ALIAS LAG` naming the ref and the canonical cell's `[select]` line; absent `:latest` → same red.
- [x] 2.3 Multi-variant engine: `:latest` probed exactly once, owned by the `cpu`-preferring canonical cell; the non-canonical cell's iteration probes no `:latest`.
- [x] 2.4 Knob off → zero `:latest` probes and unchanged tag-existence verdict.

## 3. Verification (pre-push proofs)

- [x] 3.1 `make openspec-validate NAME=latest-alias-digest-2988` exits 0.
- [ ] 3.2 `make test-unit` exits 0.
- [x] 3.3 Live gate run `ENGINE_PINS_ALIAS=1 make check-engine-pins-published ALL=1` reports one `:latest` verdict per engine (a `LATEST OK` or `ALIAS LAG` line naming each engine repo exactly once).

## 4. Records (same commit as the change)

- [x] 4.1 `agent-wiki/` dated entry naming issue #2988 and the PR, and the `docs/changes.d/` fragment consumed by `make changes-index` (`make check-docs` green).
