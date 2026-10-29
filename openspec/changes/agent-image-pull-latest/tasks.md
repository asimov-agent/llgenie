# Tasks

- [x] 1. OpenSpec change: `proposal.md`, `specs/agent-image-pull-latest/spec.md`, this checklist
- [x] 2. `scripts/ci_images.py`: agent `pull` and `ensure` fetch GHCR `:latest`; `publish agent` pushes `:latest` with a new hash and moves it with imagetools when the hash is already published; test and openspec stay on the hash
- [x] 3. `Makefile`: `agent-image`, `agent-image-pull`, `agent-image-ref`, `publish-agent-image`, and the `fix-loop-image` fallback use that ref
- [x] 4. Workflow comments in `fix-bot.yml`, `architecture-bot.yml`, `registry-sync-review.yml`, and `publish-agent-image.yml` name `:latest` as the pull
- [x] 5. Docs: `docs/BOTS.md`, `docs/ARCHITECTURE.md`, `README.md`, `AGENTS.md`
- [x] 6. Tests lock the agent `:latest` pull, the already-published retag, the test-image hash pull, and `make agent-image-ref`
- [x] 7. `agent-wiki/2026-10-29-agent-image-pull-latest.md` and `docs/changes.d/2026-10-29-agent-image-pull-latest.md`, then `make changes-index`
- [x] 8. Gates: the touched unit tests, `make openspec-validate NAME=agent-image-pull-latest`, `make check-docs`
