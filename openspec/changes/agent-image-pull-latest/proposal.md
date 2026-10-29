# agent-image-pull-latest — proposal

Issue: [#989](https://github.com/asimov-agent/llgenie/issues/989)

## Why

Publish run 40853076853 on `main` (`98466ebdb310040daaaf8c078d7f7cffc24087db`) pushed
`ghcr.io/asimov-agent/llgenie/agent:74d0fa987227` and did not push `:latest`. Every agent pull
still asks the registry for the content hash of the checkout: `scripts/ci_images.py pull` and
`ensure` call `ref()`, and `make agent-image-ref` (fix-bot, architecture-bot, registry-sync-review)
prints that hash before `docker run`. The local name `llgenie/agent:latest` is applied only after
the hash pull. A runner cannot be told to use the image last marked current.

## What Changes

- `pull agent` and `ensure agent` fetch `ghcr.io/<registry>/llgenie/agent:latest`.
- `publish agent` pushes that `:latest` tag with the content hash, and when the hash is already
  published it moves `:latest` onto the hash without a rebuild.
- `make agent-image-ref` prints the `:latest` ref. `make ci-image-refs` still prints the content hashes.
- Test and OpenSpec images keep pulling their content hashes.
- The dispatch `force` input stays unread. That gap is #990.

## Impact

- Affected: `scripts/ci_images.py`, `Makefile` agent-image targets, `fix-bot.yml`,
  `architecture-bot.yml`, `registry-sync-review.yml`, `publish-agent-image.yml`, the docs that
  described the agent pull as the Dockerfile hash, and the hermetic tests that lock those commands.
- After this merges, `:latest` does not exist until `publish-agent-image` is dispatched once.
  The already-published path moves the tag without rebuilding `74d0fa987227`.
