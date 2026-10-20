# A Strata family with no Hub URL is described, not fatal

## Why

Every Strata engine bump dies, and has since upstream added a family that is not published on the
Hub. Run `39265221145` (schedule, 2026-10-19T14:01Z):

```
bump-strata  Traceback (most recent call last):
bump-strata  KeyError: 'hf'
bump-strata  make[1]: *** [Makefile:561: sync-strata-models] Error 1
```

`scripts/strata_models.py::extract()` indexed `fam["hf"]` for every entry of Strata's `FAMILIES`
table. `nvfp4` is a vendor-hosted family — `name`, `tag`, `title`, `by`, `about`, `mmproj`,
`mmproj_sha256`, `ready`, and **no `hf`** — so the vendoring step raised before the bump could pin or
open a PR. Reproduced against Strata HEAD (`9ae93f7`) with the repo's own loader:

```
qwen has_hf=True   swift has_hf=True   coder has_hf=True
unsloth has_hf=True gyro has_hf=True   nvfp4 has_hf=False   ->  KeyError: 'hf'
```

At the current pin (`v0.1.43` / `16374b3`) all six families still carry `hf`, which is why
`make check-strata-models` is green locally and the failure only bites when the bump moves the pin.

## What Changes

- **`scripts/strata_models.py::extract()`** — a family without `hf` is recorded with its
  `title`/`file`/`shards`/`experimental` and `"hub": false`, and **no** `repo`/`revision`/`subdir`
  (nothing is invented). A family WITH `hf` is written in exactly the committed key order, because
  `check` compares the file as TEXT — at the current pin the output stays byte-identical.
- **`scripts/model_engine_pick.py`** — the three consumers learn the marker: `strata_serves()` matches
  a repo only when the family has one, `strata_first_shards()` skips a Hub-less family instead of
  building a path from `None`, and `strata_files()` raises a named `ValueError` ("not
  Hub-downloadable") instead of a `KeyError` on `repo`.
- **`tests/test_strata_missing_hf.py` (new, 5 cases)** — the Hub-less family extracts (the #416 repro),
  the Hub family keeps today's key order, the committed map carries no `hub: false` at this pin, the
  first-shard map skips it, and `strata_files` refuses it by name.
- **README** — one line: a family with no Hub URL is vendored as not Hub-downloadable.

## Impact

- Affected specs: `engine-strata-map` (new capability).
- Affected code: `scripts/strata_models.py`, `scripts/model_engine_pick.py`,
  `tests/test_strata_missing_hf.py` (new), `README.md`, `agent-wiki/`.
- No data change: `data/strata_models.json` is unchanged at the current pin (`make check-strata-models`
  stays green, byte for byte).
- The bump itself (`engine-bump.yml`) is untouched: it stops failing on this step, and any *real* bump
  finding is reported as before.

## Not covered (each its own issue)

- `registry-sync.yml`'s red run on 2026-10-19 is a different failure (the lossy store —
  andyholst/trending-local-llms#463 — plus a dead Hub link in a newly generated quant plan).
- The `nvfp4` family is not made installable here; llgenie records that it cannot fetch it from the Hub,
  which is the honest state until upstream documents a download path for it.
