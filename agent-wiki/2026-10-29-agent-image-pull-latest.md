# agent-image-pull-latest — 2026-10-29

Implements **#989**. Pull request **#992**. The unread `force` input on `publish-agent-image.yml` is **#990** and is not
part of this change.

## What changed

Publish run 40853076853 pushed `ghcr.io/asimov-agent/llgenie/agent:74d0fa987227` and no `:latest`.
Pulls asked for the content hash of the checkout (`scripts/ci_images.py ref`), then locally tagged
`llgenie/agent:latest`.

- `pull agent` and `ensure agent` now fetch `ghcr.io/<registry>/llgenie/agent:latest`.
- `publish agent` tags that `:latest` beside the content hash. When the hash is already published,
  `buildx imagetools create` moves `:latest` onto it and does not rebuild. Test and OpenSpec
  publishes stay hash-only.
- `make agent-image-ref` prints `:latest`. fix-bot, architecture-bot, and registry-sync-review
  still resolve the image through that target before `docker run`. `make ci-image-refs` still
  prints the three content hashes.
- `:latest` does not exist on GHCR until `publish-agent-image` is dispatched once after this
  merges. That dispatch is not part of this change. The already-published path is what points
  `:latest` at `74d0fa987227` without a rebuild.

## Verified

Hermetic tests with a fake `docker`: agent pull and ensure request `:latest`, a new agent publish
tags `:latest`, an already-published agent hash runs `imagetools create` and no build, and the
test-image pull is still the 12-hex hash. `make -n agent-image-ref` prints
`python3 scripts/ci_images.py latest agent`.
