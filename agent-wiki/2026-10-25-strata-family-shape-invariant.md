# strata: the family SHAPE is the invariant, not v0.1.43's membership

Issue: #643 — the Strata Hub-flag test pins the v0.1.43 data snapshot (opened by andyholst; its body
names #605 and #416). Related: #605 (the correct v0.2.4 bump it red), #641/#642 (the
rebase-bot truncation that kept #605 `DIRTY`, deliberately out of scope).
PR: opened by the issue-bot job from this tree (`pr-body.md` at the repo root).

## What was wrong

`tests/test_strata_missing_hf.py::test_the_committed_map_states_no_hub_flag_at_the_current_pin`
asserted "no family carries `hub: false`" — the literal membership of `data/strata_models.json` at
pin v0.1.43. At v0.2.4 the pinned `setup.py` declares `nvfp4` with no `hf`, so `make
sync-strata-models` correctly wrote `hub: false` and the test failed with `nvfp4 unexpectedly marked
not-Hub` (`1 failed, 5123 passed, 6 deselected` on `#605`). The sibling live test
(`test_map_tables_equal_setup_py_tables`) had the same latent bug: it indexed `d["repo"]` for every
family and would have raised `KeyError` once the live tier ran at v0.2.4.

## What changed

- `scripts/strata_models.py::family_shape_problems()` is the invariant as product logic: a family is
  Hub-hosted (`repo` + `revision` + `subdir`, no `hub` key at all) or explicitly not-Hub
  (`hub: false`, no repo/revision/subdir) — never both, never neither. `subdir` may be `""` (Strata's
  `swift` is published at the repo root) but must be present.
- `strata_models.py check` (`make check-strata-models`) runs it on the committed map, so a malformed
  map is reported by family and defect (`nvfp4: marked not-Hub (hub: false) but carries a repo`)
  instead of only as a 100-line diff. The pinned byte comparison is unchanged and still the drift
  guard.
- The snapshot test is replaced by: the committed map satisfies the rule and names the skill's pin;
  both pins (v0.1.43 all-Hub, v0.2.4 with `nvfp4`) satisfy the same rule; each genuine defect is
  named; the not-Hub set is derived from the `setup.py` being extracted, never listed.
- The live tier reads a Hub-less family's shape instead of crashing, and asserts the map's not-Hub set
  equals the *fetched* pinned `setup.py`'s.
- `openspec/changes/strata-family-shape-invariant` records the behaviour; the #416 change's scenario
  whose test this replaces now points at the replacement instead of a deleted test name.

## Verified

- Reproduced the reported failure, then the fix: with a v0.2.4-shaped tree (map + skill pin at
  `0303f658`, `nvfp4` `hub: false`) the OLD test failed (`nvfp4 unexpectedly marked not-Hub`) and the
  new tests passed 9/9; on the restored v0.1.43 tree they pass 9/9 too.
- `make check-strata-models`' named-failure path is covered by
  `test_check_names_a_malformed_map_instead_of_only_a_diff` (real `strata_models.py check` run, exit 1,
  message asserted).
- Hermetic gates run in the agent container: `python3 scripts/unit_tests.py run` (the aggregator
  `make test-unit` drives — **5182 passed, 6 deselected in 821s, exit 0**; the container wrapper could
  not be used, there is no Docker daemon here), `python3 scripts/lint_linefeeds.py`,
  `make check-wiring` (OK, 199 documents), `make check-docs` (OK, 199 targets / 172 records),
  `make openspec-tasks-check NAME=strata-family-shape-invariant`. `make
  openspec-validate` could not run here: the container has no Docker daemon and no node/npm, so the
  Dockerized OpenSpec CLI is unavailable; the change directory follows the CLI's layout and the
  existing changes' format.
- The live tier (`make test-strata-live`) needs Strata's pinned commit over git and the live Hub; it
  was not run in this container.
