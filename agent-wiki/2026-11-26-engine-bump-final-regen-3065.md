# 2026-11-26 — engine-bump final generation gate: a bump can no longer commit a binaries manifest that lags its own skill (issue #3065)

## What was verified against the issue

- The issue's symptom was root-caused from the red lane itself before any code: at PR #3029's head
  `4958f3953` the commit carries `containers/engines/params/ollama.json` + `skills/engines/ollama/SKILL.md`
  + the four Dockerfiles at `0.40.17`, but `containers/engines/binaries.json` still names
  `/opt/llgenie/engines/ollama/0.40.16/bin/ollama` on all four variants. `scripts/engine_image.py`'s
  `binary_manifest` reads exactly that committed manifest, so all four `engine-build-ollama-*` probes
  failed "probed non-zero (1)" (runs 45242586633 / 45245255181 / 45255816977 / 45281314211), and the
  PR's unit gate failed `test_committed_engine_params_match_the_skills` ("run make
  generate-engine-params: ['containers/engines/binaries.json']", run 45242536729).
- The fix shape was reproduced at that head in a detached scratch worktree: `make
  generate-engine-params ENGINE=ollama` (i.e. `scripts/engine_skills.py params --only ollama`) updates
  exactly the four ollama manifest entries — proving the committed tree was stale-vs-generated, not
  the generator.
- The producer now carries a FINAL gate (`scripts/engine_bump.py::_final_generation_gate`, called at
  the end of `bump()` after `_rewrite_frozen_hashes` + `_write_companion_notes`): `make
  check-engine-params` runs FIRST (a converged tree issues no regen at all); on a stale verdict it
  re-runs `_regen_guard` once (nag-at-most-once) and re-checks; a second stale verdict hard-fails the
  bump with the checker's verdict quoted. The final regen's paths join the bump's reported `regen:` set.

## Key decisions

- Check before regen: the gate is a verification, not an unconditional regeneration — the common
  (already-converged) bump pays only one `check-engine-params`.
- Nag-at-most-once, then hard-fail: a bump PR whose manifest cannot converge is refused rather than
  shipped red — the #3065 lane would have been caught before its four red image builds.
- The red #3029 lane is re-armed with its regenerated manifest pushed onto
  `chore/engine-bump-ollama` (this change's second half), keeping the diagnosis and its remediation
  under one goal.

## Current status

Producer gate + 3 hermetic tests land on `feat/engine-bump-final-regen-3065`; the re-armed #3029 head
and the full unit battery are recorded in the PR body's acceptance criteria.
