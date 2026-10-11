# 2026-10-11 — bump PR body newlines, pin-assert rewrite, damaged-GGUF refetch

PR #145, one commit on latest `main`, OpenSpec change
`fix-engine-bump-pr-body-newlines`, issue #144. All tasks ticked.

Verified:

- `engine-bump.yml` builds the PR body with `printf`, so `\n` is a real newline.
  `tests/test_engine_bump_pr_body.py`: 5 passed.
- `engine_bump.bump` rewrites the old pin in `tests/` and `README.md` (full sha,
  8-char prefix, tag, tag without `v`) and regenerates `data/strata_models.json`
  for Strata. A dry run over the real tree moved the ollama `v0.35.1` asserts and
  the prism `2459f68b` tag, and left vllm/sglang alone.
  `test_bump_rewrites_hardcoded_pin_asserts` passed.
- `download_top_tier_candidate` removes a same-size file that is not a readable
  GGUF and fetches it once more. This is the `macos / top-tier` failure (job
  114411102221, `test_same_name_updated_model_is_redownloaded`).
  `test_unreadable_gguf_is_removed_and_refetched` passed.
- `make lint` and `make openspec-validate NAME=fix-engine-bump-pr-body-newlines`
  exited 0.

Not run: the full `make test-unit` and `make ci-top-tier` (real 430 MB download).
The published engine tests never compare a binary version to the pinned sha.
Squashed to one commit and force-pushed to the fork; local HEAD, fork HEAD and
the PR head are the same sha.
