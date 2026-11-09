# registry-sync-test-unit-e2big — Tasks

Checklist of record. The registry-sync change-path `make test-unit` step scopes the
job-level `HF_TOKEN`/`GITHUB_TOKEN`/`GH_TOKEN` env (re-pointing the token vars at
`${{ github.token }}`, `HF_TOKEN` empty) so the gh-spawning tests no longer inherit a
large secret env and die `OSError: [Errno 7] Argument list too long` (issue #2395),
letting the sync PR open; a regression probe (the container repro + the fixed workflow)
proves both the bug and the fix.

## Change-path test-unit env scoping

- [x] 1.1 The change-path check/test-unit step re-points the env at the step level:
      `HF_TOKEN` empty, `GITHUB_TOKEN`/`GH_TOKEN` = `${{ github.token }}` (small, non-empty)
- [x] 1.2 No gate, check or permission is removed or relaxed; the gh-spawning tests still run
- [x] 1.3 The change is byte-identical in effect to push CI's `linux / unit` (no job-level
      secret values, and `engine_bump_rebase.load_token()` still finds a non-empty token)

## Regression evidence

- [x] 2.1 In `ghcr.io/asimov-agent/llgenie/test:7df351360413`, a large forwarded `HF_TOKEN`
      makes the three tests die `Argument list too long` (bug reproduced)
- [x] 2.2 With the env scoped small the same three tests pass (`3 passed`, fix proven)
- [x] 2.3 `scripts/check_workflows.py check` passes at the head

## Docs + verification (final)

- [x] 3.1 OpenSpec `proposal.md` / `spec.md` / `tasks.md` written and
      `make openspec-validate NAME=registry-sync-test-unit-e2big` passes
- [x] 3.2 `agent-wiki/2026-11-09-registry-sync-test-unit-e2big-2395.md` note (references
      #2395) and a `docs/changes.d/2026-11-09-registry-sync-test-unit-e2big-2395.md`
      index fragment, committed with the change
- [x] 3.3 `make check-docs` change->note gate passes at the head
