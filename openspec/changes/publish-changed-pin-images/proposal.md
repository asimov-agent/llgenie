# ci: publish only engine images whose tag changed

Issue: [#153](https://github.com/asimov-agent/llgenie/issues/153)

## Why

A push to `main` rebuilds and republishes every engine image. The published
tag is `llgenie/<id>:<pin8>-<image-hash>-<arch>`, so an unchanged tag is
already on GHCR. Rebuilding it spends a runner and rewrites the moving
`:<arch>` tag for no change. The matrix is scoped to changed params only on
`pull_request`; a `push` always runs the full matrix.

## What Changes

- `matrix(changed=<ref>)` keeps an engine×arch image only when its image tag
  differs from `<ref>`. The tag moves when the pin hash moves, when that
  variant's params or its committed Dockerfile change, or when a file every
  image is built from changes (`entrypoint.sh`, `engine_runner.py`).
- The tag hash keeps the framing the published tags were built with: variant
  params + committed Dockerfile + `entrypoint.sh` + `engine_runner.py`,
  concatenated. The first cut joined those parts with NUL bytes instead, which
  moved all 31 engine×arch tags at once while the scoped matrix rebuilt none
  of them — every install job then asked GHCR for an image that had never been
  pushed (`[install] FAIL llama.cpp/cpu: not published`) and `linux / install`
  plus all four `install-published-*` jobs went red. `engine_skills._image_inputs`
  is now the one place that framing lives, and `_tag_at` / `_current_tag` both
  go through it.
- The push path in `ci.yml` passes `CHANGED` too: `github.event.before` on a
  `main` push, the PR base on `pull_request`. A first push of a branch (before
  is all zeros) keeps the full matrix.
- A push that changes no image tag publishes nothing. The `none` placeholder
  row stays, so an empty include list never fails the workflow.
- `tests/test_engine_image_matrix.py` is added to `make test-unit` (the CI
  `unit` job). Before this it was run by no gate at all.
- New tests lock the tag itself: the published digest, that every hashed input
  moves the tag, that the matrix's tag is exactly the tag `make install` pulls,
  that every matrix row is an engine×arch `make build-engine` can build, and
  the scoping behaviour measured on this repo's real committed build inputs
  (13 engines, 31 variants) in a scratch git repo — no GHCR push needed.
- Every Hub call sends `HF_TOKEN` (environment, else `~/.zshrc` / `~/.bashrc`).
  CI sets that variable from the `HF_TOKEN` Actions secret and passes it into
  the reusable workflows with `secrets: inherit`.
- For every engine, a moved pin is tested to expand to the make commands CI
  runs for that engine's CI variants: `build-engine`, `test-engine-stage` and
  `push-engine`, with `ENGINE`, `ARCH` and `TEST` from the matrix row.

## Impact

- `scripts/engine_image.py`, `scripts/engine_skills.py`, `scripts/hf_auth.py`,
  `.github/workflows/ci.yml`, `pipeline.yml`, `published.yml`,
  `Makefile`, `README.md`
- `tests/test_engine_image_matrix.py`, `tests/test_hf_auth.py`
