# strata-repin-v0-2-11

## ADDED Requirements

### Requirement: Strata is re-pinned to the newest all-variants-buildable release

The strata engine skill `ref`/`version`/`pinned` SHALL name v0.2.11@4a4160162e4a402e082f41aa0a88e6eed629d913 — the newest release whose `src/prefill/prefill.cpp` carries zero `fused::want_dm_f16` call sites, so both the cuda and the rocm CI cells can link and build green at the pin.

WHEN the skill and its generated artifacts are read
THEN `skills/engines/strata/SKILL.md` names v0.2.11 / 4a4160162e4a402e082f41aa0a88e6eed629d913, and `containers/engines/params/strata.json` and both `Dockerfile.*` frozen variants embed the same pin with no stale v0.2.9 token.

#### Scenario: the skill names the new pin

Given the strata skill's front matter
When  `ref`, `version` and `pinned` are read
Then  they are `v0.2.11`, `v0.2.11` and `4a4160162e4a402e082f41aa0a88e6eed629d913`, and no `d94bac6a` / `v0.2.9` token remains in the skill.

- **Test:** `make check-engine-params` regenerates the committed params from the skill and reports no drift (the generated params gate).

#### Scenario: the frozen variants build from the new pin

Given the committed params and Dockerfiles for strata
When  they are regenerated from the skill via `make generate-engine-params ENGINE=strata`
Then  both `cuda` and `rocm` variants carry the new pin and the exact v0.2.11 install clone/checkout steps, so each `make build-engine ENGINE=strata ARCH=<backend>` cell describes the same source the engine-build lane compiles.

- **Test:** `make check-engine-params` (green = committed output equals what the skill generates).

#### Scenario: the Strata model map matches setup.py at the new pin

Given `data/strata_models.json`
When  it is regenerated via `make sync-strata-models`
Then  it is built from Strata's setup.py at the pinned commit, so `make check-strata-models` stays green and the picker serves the families Strata actually supports at v0.2.11.

- **Test:** `make check-strata-models`

### Requirement: the v0.2.13 bump is deferred upstream, not abandoned

The re-pin SHALL NOT smuggle an uncommitted second code path or an option change; the broken v0.2.13 link fix is upstream Niko1221/Strata#5473, and re-attempting the bump is tracked as a separate piece of work, not folded into this change.

WHEN the change is reviewed
THEN it moves only the pin and its generated artifacts, and carries no `STRATA_PREFILL_MMQ`/`STRATA_NATIVE_EXPERTS` enablement and no vendored link stub.

- **Test:** the diff is exactly the skill pin, the regenerated params + Dockerfiles, and the re-synced strata_models.json (plus this OpenSpec change and its documentation).
