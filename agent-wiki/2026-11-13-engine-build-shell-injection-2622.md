# engine-build shell-injection fix (#2622)

Issue: #2622 · PR: #2624 · OpenSpec: `engine-build-shell-injection`

## What was verified

- The finding: semgrep `github-actions.security.run-shell-injection` (high) at
  `.github/workflows/engine-build.yml:149` — the #2578 Dispatch provenance step ran
  `producer="${{ inputs.producer_run }}"`. Expression expansion happens before the
  shell parses the line, so a dispatch value with `"` or `$( )` executes.
- It surfaced on `main` `2f6574ea8` when #2621's verification battery re-ran
  `make security-scan-all` (rc=0) + `make security-verdict EVENT=schedule`: it was the
  ONLY blocking finding left (event=schedule, mode=full) after #2608/#2610/#2611 fixed
  the previous two. Filed by `make security-issues` as #2622; cross-linked both ways
  with #2621.
- The fix: `env: PRODUCER_RUN / TRIGGERING_ACTOR` bindings; the shell reads variables
  only. Lock test `test_liveness_dispatches_name_their_producer_run` extended with the
  #2622 assertions (no GitHub expression in the step's shell body, both env bindings
  present, step extent bounded at the `matrix:` job header — provenance is the guard
  job's last step, so the old `- name:` slice bleeds into the next job).
- Proof measured on the branch: hermetic `pytest tests/test_check_engine_pins_published.py`
  → 30 passed rc=0; `make security-scan TOOL=semgrep` (pinned digest
  `sha256:180c3f7e5696…`) → 0 run-shell-injection findings at engine-build.yml
  (43 repo-wide findings otherwise unchanged); `make check-workflows` OK.

## Key decision

The first fix attempt failed `make check-workflows`: the explanatory step comment
quoted an empty `${{ }}` token, and GitHub parses EVERY expression in the file's raw
text — comments included (issue #330's silent 0-job refusal class). Comments now avoid
expression syntax entirely.

## Current status

Fix implemented + verified on `feat/engine-build-shell-injection`; PR opened; the daily
security-scan verdict clears when this merges.
