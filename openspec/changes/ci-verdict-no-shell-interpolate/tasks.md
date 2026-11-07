# Tasks

- [x] Reproduce the finding at origin/main with the repo's pinned semgrep image and confirm `check_id=yaml.github-actions.security.run-shell-injection.run-shell-injection` at `.github/workflows/ci-verdict.yml:159`
- [x] Confirm the flagged value (`inputs.head_sha`) is a genuine shell-injection surface (GitHub expands `${{ }}` before the shell) and not a false positive
- [x] Add `HEAD_SHA: ${{ inputs.head_sha }}` to the "Read the finished run" step's `env:` block and reference `"$HEAD_SHA"` in its `run:` block in place of `"${{ inputs.head_sha }}"`
- [x] Prove the fix with the pinned semgrep image: 0 matches on the fixed head, the rule still matching at the flagged region on the pre-fix file
- [x] `make openspec-validate NAME=ci-verdict-no-shell-interpolate` passes
- [x] Add the agent-wiki note + docs/changes.d fragment naming issue #1972 and the merged fix PR; `make changes-index` + `make check-docs` + `make lint` green
- [x] `make lane-preflight` green on the pushed branch
