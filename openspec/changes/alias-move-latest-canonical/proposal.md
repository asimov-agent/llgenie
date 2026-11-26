# alias-move-latest-canonical — heal the engine's `:latest` alias when the canonical variant lags

## Why

`make engine-alias-move` (issue #2996) moved only each lagging cell's `:<variant>` alias. The
full-fleet gate (PR #3003 / issue #2988) holds every engine's `:latest` tag to its canonical
variant's committed pin digest. A registry-liveness heal therefore moved the variant half and
re-redded on `:latest` forever — six `ALIAS LAG` lines, `fleet_rc=2` at main `3cea715e3`
(run `45773544133`). The battery could never self-heal its declared gap class.

## What changes

`scripts/engine_alias_move.py::move_alias` keeps its four-field contract and its byte-preserving
fetch + refusal rails. After the variant alias has been published AND verified at the pin digest,
the mover checks the SAME ownership rule the gate and publisher use —
`engine_image.engine_latest_variant(engine_image.resolve(engine, None, variant)) == variant`.
For the canonical variant only, it re-publishes the identical fetched manifest bytes to
`/manifests/latest` with the manifest's own mediaType and verifies `:latest` at the same pin
digest through the same probe seam. Non-canonical cells remain variant-only.

No new CLI field, no engine run, no image build: the change is a second manifest PUT through the
existing fakeable `put`/`probe` seams.

## Out of scope

- The post-merge live heal of the six currently-lagging tags on GHCR, and the registry-liveness
  main-run green read (issue #3080 AC-2/AC-3) — this lands through the normal landing flow.
- The fleet gate itself (`scripts/check_engine_pins_published.py`): verify-only, unchanged.
- Publisher/build paths: `engine_image.push` already points `:latest` at this variant.
