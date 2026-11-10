# Fixing a workflow gate that reads a stale event snapshot

A gate defect of the class: the workflow job passes PR body/metadata from the run's
**immutable event snapshot** (`PR_BODY: ${{ github.event.pull_request.body }}`). That snapshot is frozen
when the run is created; only a new push re-snapshots it. So a body-only or metadata-only fix (adding the
adjacent `closes #N`, correcting a title) never clears the gate on `gh run rerun` — it keeps reading the old
text. The fix is to read the value **live** inside the run step.

## Recipe

1. **Read live in the run step, not in `env:`.** Fetch the body from the API and write it to the file the
   recipe already reads:
   ```bash
   PR_BODY="$(gh api "repos/$PR_REPO/pulls/$PR_NUMBER" --jq '.body // ""')"
   printf '%s\n' "$PR_BODY" > /tmp/pr-body.md
   export PR_BODY=/tmp/pr-body.md
   make check-pr-closing
   ```
   Fall back to `''` on a non-PR event (a `push` to main has no pull request); `// ""` handles a null body.
2. **Pass repo/number via `env:`, never inline in the run block.** Use `PR_REPO: ${{ github.repository }}`
   and `PR_NUMBER: ${{ github.event.pull_request.number }}`. A shape test asserts the run block contains
   **no** `${{` (`assert "${{" not in run`) — an inline expression reds it. This is the "shape change has a
   spelling" trap: before editing any step's run block, grep `tests/` for that step's assertions (they read
   the YAML and assert on substrings like `export PR_BODY=/tmp/pr-body.md`, `PR_BASE:`, and expression-freeness).
3. **Permissions: the live read needs `pull-requests: read`.** A `scope`-style workflow that declares only
   `contents: read` must gain `pull-requests: read` — a read-scope **addition**, never a weakening. A `ci`-style
   guard job inherits the default token and usually already has it; confirm before adding.
4. **Prove do-not-weaken.** The rule file (`scripts/check_pr_closing.py`) and its Makefile recipe must stay
   **byte-identical vs base** (`git diff <base> -- scripts/check_pr_closing.py Makefile` → 0), and the gate
   must still red on a genuine non-adjacent close. Scanning/routing is half the control — do not relax the
   catch to make the change land.

## Verify end-to-end (do not stop at "the YAML looks right")

- Reproduce the step's live read exactly and confirm it returns the CURRENT body (has the adjacent `closes #N`).
- Feed that live body to the real recipe and require `rc=0` + `[check-pr-closing] OK`:
  `make check-pr-closing PR_BODY=/tmp/pr-body.md`.
- Run the workflow-reading shape tests (a workflow edit reds these if it breaks an assertion):
  `pytest tests/test_check_pr_closing.py tests/test_workflows_valid.py tests/test_ci_scope.py tests/test_pin_actions.py tests/test_wiring.py tests/test_ci_images.py`.
  All green is the proof a workflow edit did not red a shape guard you did not grep for.

## Pitfall: a stale fork ref turns a local gate run into a false red

Running `make check-pr-closing` in a worktree whose `origin/main` is the **fork** (stale, far behind) makes
`git merge-base origin/main HEAD` resolve far back, so the squash range sweeps in **all upstream history** and
the gate reds with "the joined commit messages claim #15xx, #15xx…" for issues you never touched. This is a
local-ref artifact, not your change. Verify against the true base — `git rev-list --count upstream/main..HEAD`
must be 1 (your single commit) — then run
`make check-pr-closing PR_BODY=/tmp/pr-body.md PR_BASE=upstream/main`. The CI job refreshes the base per run,
so the local red is not the gate's verdict. Always state the measured base sha alongside any local gate result.
