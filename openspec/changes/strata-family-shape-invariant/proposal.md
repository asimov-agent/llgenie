# strata-family-shape-invariant — proposal

Issue: [#643](https://github.com/asimov-agent/llgenie/issues/643) — the Strata bump to v0.2.4
([#605](https://github.com/asimov-agent/llgenie/pull/605)) went red on one test that describes the
*previous* pin.

## Why

`tests/test_strata_missing_hf.py::test_the_committed_map_states_no_hub_flag_at_the_current_pin`
asserted the literal contents of `data/strata_models.json` at pin v0.1.43:

```python
for name, fam in committed["families"].items():
    assert fam.get("hub") is not False, f"{name} unexpectedly marked not-Hub"
    assert fam["repo"], f"{name} is Hub-hosted at this pin"
```

Its own docstring admitted it ("at the current pin every family is Hub-hosted, so nothing new is
written"). At v0.2.4 the pinned `setup.py` declares `nvfp4` as vendor-hosted with **no `hf` key** —
exactly the family `scripts/strata_models.py` was hardened for in [#416](https://github.com/asimov-agent/llgenie/issues/416) —
so `make sync-strata-models` correctly wrote `hub: false` for it and the assertion failed with
`nvfp4 unexpectedly marked not-Hub`.

Measured: `#605` (`chore/engine-bump-strata`, v0.2.4@`0303f658`) — `linux/unit` and `macos/unit` fail
on this test alone, `1 failed, 5123 passed, 6 deselected`. The bump regenerated
`data/strata_models.json` (+106/−12), `containers/engines/params/strata.json` (+16/−10), both
Dockerfiles and the skill; nothing about it was wrong.

The defect is a **test that pins a data snapshot instead of the invariant**: every future Strata bump
that surfaces a Hub-less family is red for a correct reason, so the bump is blocked and the engine
silently ages. `tests/test_strata_download.py::test_map_tables_equal_setup_py_tables` carried the same
latent bug (it indexed `d["repo"]` for every family, and would have died on `nvfp4` with a `KeyError`
the moment the live tier ran at v0.2.4).

## What Changes

- **`scripts/strata_models.py::family_shape_problems()`** (new) states the invariant once: a family
  is Hub-hosted (`repo` + `revision` + `subdir`, and **no** `hub` key at all) or explicitly not-Hub
  (`hub: false`, and no repo/revision/subdir) — never both, never neither. `subdir` may be `""` (a
  family published at the repo root — `swift` is) but must be present. It returns the problems by
  family name, so a caller prints *what* is wrong instead of a diff.
- **`make check-strata-models` uses it** (`strata_models.py check`): a map that breaks the rule now
  fails with `nvfp4: marked not-Hub (hub: false) but carries a repo` rather than only
  "differs from Strata's setup.py". The byte comparison that guards drift stays exactly where it was.
- **The snapshot test is replaced by the invariant** in `tests/test_strata_missing_hf.py`: the
  committed map must satisfy the rule (whatever set of families the pin declares), be the pin the
  skill names, and the rule must reject each genuine defect (both shapes at once, neither, `hub:
  true`, a URL that was never split). The not-Hub *set* is derived from the `setup.py` being
  extracted, never written as a list in the test — so the next bump cannot red it.
- **`tests/test_strata_download.py`** (the live tier, which fetches the pinned commit) now reads a
  Hub-less family's shape instead of crashing, and asserts the committed map's not-Hub set equals the
  **pinned** `setup.py`'s — the derivation from the pin itself.

## Impact

- A correct Strata bump no longer fails on a test that describes the previous pin.
- The real invariant — *a family is Hub-hosted or explicitly not, never ambiguous* — is locked at any
  pin, and its violation is named by family.
- No change to the generated map, the Dockerfiles or the consumer paths (`strata_files`,
  `strata_first_shards` already skip a Hub-less family, covered in #416).

## Not covered

- The `rebase-bot` truncation that kept `#605` `DIRTY` — issue #641 / PR #642.
