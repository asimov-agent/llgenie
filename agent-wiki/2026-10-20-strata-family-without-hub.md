# The Strata bump stopped dying on a family that has no Hub URL

Issue #416. OpenSpec change: `strata-family-without-hub`. PR: (this branch, opened against `asimov-agent/llgenie:main`).

## What was wrong

`engine-bump.yml`'s `bump-strata` job has been red since Strata added `nvfp4` — a vendor-hosted family
with `name`/`tag`/`title`/`mmproj_sha256`/`ready` and **no `hf`**:

```
bump-strata  Traceback (most recent call last):
bump-strata  KeyError: 'hf'
bump-strata  make[1]: *** [Makefile:561: sync-strata-models] Error 1
```

Run `39265221145` (2026-10-19T14:01Z). `scripts/strata_models.py::extract()` indexed `fam["hf"]`
unconditionally, so the vendor step died before the bump could pin or open a PR — Strata has had no
engine bump since. At the *current* pin (`v0.1.43` / `16374b3`) all six families still carry `hf`,
which is why `make check-strata-models` passes locally and the bug only bites when the pin moves.

Reproduced at Strata HEAD (`9ae93f7`) with the repo's own loader: `qwen`, `swift`, `coder`, `unsloth`,
`gyro` have `hf`; `nvfp4` does not.

## What changed

- `scripts/strata_models.py::extract()` — no `hf` ⇒ `{"title", "hub": false, "file", "shards",
  "experimental"}` and no repo/revision/subdir (nothing invented). WITH `hf` ⇒ the committed key order,
  because `check` compares the file as TEXT.
- `scripts/model_engine_pick.py` — `strata_serves()` needs a repo to match, `strata_first_shards()`
  skips a Hub-less family, `strata_files()` raises a named `ValueError` instead of a `KeyError: 'repo'`.
- `tests/test_strata_missing_hf.py` — 5 cases: the #416 repro, the committed key order, byte-stability
  at the pin, the skip, the named refusal.
- README line: a family without a Hub URL is vendored as not Hub-downloadable.

## Verification

- `pytest tests/test_strata_missing_hf.py` → 5 passed.
- `make check-strata-models` → still matches Strata's setup.py at the pinned commit (byte-identical).
- Negative control: the same `check --src /tmp/strata-head` with the OLD code → `KeyError: 'hf'` (rc=1);
  with the new code → a normal "differs from the pinned commit" report. That is the bump no longer
  crashing.
- `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=strata-family-without-hub`,
  `make test-unit`.

## Honest limits

- `nvfp4` is still not installable through llgenie: recording "not Hub-downloadable" is the honest state
  until upstream documents a download path for the family. The bump can now proceed past it.
- `data/strata_models.json` is untouched, so nothing about today's pinned runtime changes.
- The bump PR path itself is unchanged; a real bump finding still reports as before.
