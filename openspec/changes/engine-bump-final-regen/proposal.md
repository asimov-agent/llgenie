## Why

The ollama bump #3029 (issue #3065) built red on all four image variants because its commit left
`containers/engines/binaries.json` at the OLD version paths (`.../ollama/0.40.16/...`) while the skill
and params named `v0.40.17`. The image probe (`scripts/engine_image.py`, via `binary_manifest`) reads
that committed manifest, so every variant failed "probed non-zero (1)", and the PR's own unit gate
(`test_committed_engine_params_match_the_skills`) failed with "run make generate-engine-params:
['containers/engines/binaries.json']". The bump producer DOES run regen (`_regen_guard`), but its LAST
skill-adjacent writes (`_rewrite_frozen_hashes`) happen AFTER regen, and nothing re-verifies the
generated companions before the bump commits. A bump must not be able to commit a tree whose generated
manifests lag the skill the same commit rewrote.

## What Changes

- `scripts/engine_bump.py::bump` gains a FINAL generation gate after all writes: run
  `make check-engine-params`; if it names a stale generated file, re-run `make generate-engine-params
  ENGINE=<id>` once (nag-at-most-once), re-check, and hard-fail the bump if the tree is STILL stale.
  The final regen's changed paths join the bump's reported `regen:` set.
- The `## Not covered` half of issue #3065 — re-arming the #3029 lane itself (pushing the regenerated
  manifest onto `chore/engine-bump-ollama` so its probes can pass) — is executed as a ship action of
  this change, keeping #3029's green attempt and the producer fix under one goal.

## Impact

- Affected specs: `engine-bump` (bump must land with generated companions in sync)
- Affected code: `scripts/engine_bump.py`, `tests/test_engine_bump.py`
- Affected lanes: the weekly engine-bump producer lane; every future pin-bump PR
