# Tasks — strata-check-offline

- [x] `scripts/strata_models.py`: `sync` also vendors the fetched `setup.py` verbatim to
      `data/vendor/strata/setup.py` and writes `data/vendor/strata/manifest.json`
      (`url`, `ref`, `pinned`, `bytes`, `sha256`); `check` becomes hermetic — assert manifest
      pin == skill pin, assert vendored sha256 == manifest sha256, derive `want` from the vendored
      `setup.py`, keep the family-shape problems report and the text comparison; add `check-live`
      carrying the old fetch-then-compare path (no `--src` → checkout).
      (realized a bit wider than first drafted: the vendor covers setup.py's whole module-level
      import closure with a per-file sha256 `files` map, because the pinned setup.py imports
      `strata_control.acquisition` at module level — a lone setup.py cannot be imported)
- [x] Vendor the current pin now: run `make sync-strata-models` once so `data/vendor/strata/`
      enters the tree with the committed map already matching (json content unchanged).
- [x] Wire it: `check-strata-models` help line restated (hermetic), new `check-strata-models-live`
      target in `mk/engines.mk` with a non-CI-claiming help line, both in the Makefile target
      roster and the `.PHONY` block; `scripts/ci_unit.py` step list unchanged;
      `engine-bump.yml`'s `git add` carries `data/vendor/strata/` so a pin bump commits the
      regenerated vendor beside the map.
- [x] Tests (update existing, add the hermetic proofs): hermetic `check` green with every
      `subprocess` spawn refused; hand-edited map red; manifest-pin-vs-skill-pin mismatch red;
      tampered vendor digest red; `sync --src <fixture>` writes vendor+manifest+json; the live
      subcommand exists and is the only path that names `checkout()`; the ci-unit stage fixture
      still names `make check-strata-models`. (29 passed: hermetic + missing_hf + live_target +
      ci_unit_stage modules)
- [x] Docs: `docs/BOTS.md` + `docs/ARCHITECTURE.md` reflect the hermetic/live split; dated
      `agent-wiki/2026-11-19-strata-check-hermetic-519.md` entry; `docs/changes.d/` row +
      `make changes-index` (908 fragments).
- [x] Issue #519 body restated to the six-section form, ACs ticked with replayable proven tokens.
- [x] Gates: `make test-unit`, `make openspec-validate NAME=strata-check-offline`,
      `make lane-preflight` green at the pushed head; PR body mirrors the issue ACs; commit text
      mirrors them as `- [x]` lines. (openspec-validate already rc=0)
