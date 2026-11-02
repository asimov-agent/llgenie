# all-pipelines bot dispatch verifiable: guard carve-out + sweep dispatch-at-own-ref (#1571)

2026-11-02. The weekly all-pipelines sweep (`.github/workflows/all-pipelines.yml`, issue #1102)
dispatches every active workflow as `github-actions[bot]`, but each target's trigger guard admitted
the bot ONLY on a same-repo PR head (`HEAD_REPO == REPO`). A `workflow_dispatch` has no PR head, so the
bot (not a collaborator) was refused before any secret was read — six active pipelines (arms,
ci-requeue, engine-build, engine-bump, holds, publish-agent-image) redded by design and the sweep could
never verify them via its own dispatch.

## Fix

1. **Every guard site** (`.github/workflows/*.yml`, byte-identical `Owner / collaborator trigger
   guard`) gains `EVENT`/`REF` env and a second bot allowance: admit `github-actions[bot]` when
   `EVENT == workflow_dispatch`. A `workflow_dispatch` can only be started by a token with write access
   to THIS repository and can only target THIS repo's own refs, so the event itself IS the same-repo
   guarantee — the same-repo-head intent reached via event instead of the (empty) HEAD_REPO. A bot on a
   foreign PR head (`HEAD_REPO != REPO`) or a non-dispatch event with no head is still refused
   (#495/#510 unchanged).
2. **`all-pipelines.yml` sweep step** now passes `REF="${{ github.ref_name }}"` — the sweep sweeps the
   tree it is running (a PR-head sweep verifies the PR-branch guarded workflows; a weekly-on-main sweep
   verifies main), making a pre-merge green sweep provable.
3. **`scripts/all_pipelines.py`** — when a dispatched run concludes `failure` at its own `guard` job
   (the rest skipped), the table renders `NOT VERIFIED — refused at its own trigger guard`, naming the
   workflow and the reason instead of a bare `completed/failure`.

## Tests / acceptance

- `tests/test_workflow_guards.py`: bot + `workflow_dispatch` (any of the repo's own refs) -> allowed;
  bot + non-dispatch event (no head) -> refused (negative control); existing same-repo / foreign-head /
  no-head execution tests all still pass.
- `tests/test_all_pipelines.py`: a guard-refused run renders `NOT VERIFIED — refused at its own trigger
  guard` (never a bare `completed/failure` cell); a genuinely-failed pipeline keeps `completed/failure`;
  the verdict flag is proven from a real `/actions/runs/{id}/jobs` shape via the stub.
- `make check-workflows`, `make check-wiring`, `make openspec-validate NAME=sweep-bot-dispatch` pass.
- Live: `gh workflow run all-pipelines.yml` at the PR head (green run id recorded in the PR).
