# workflow-flow-targets — a `Flow:` header must name targets that exist (issue #323)

Implements **#323**, found while exercising `publish-agent-image.yml` as a bot dispatcher.
Out-of-scope finding filed as its own issue: **#335** (the push pre-flight the README promised).

## The finding

`publish-agent-image.yml`'s header documented a flow that includes a make target that does not exist:

```
# Flow: guard -> make agent-image-ref (the hash of this commit's Dockerfile + install script)
#       -> make agent-image-push-check -> make publish-agent-image (build, and push to GHCR when
#       that hash is not there yet).
```

`grep -n "push-check" Makefile` → nothing. The job's real steps are `make publish-agent-image` (whose
recipe is `python3 scripts/ci_images.py publish agent`) and `make ci-image-refs`; the "is this hash
already on GHCR" decision lives *inside* `ci_images.py publish`, not in a make target.

The same target was documented in `README.md` as a real pre-flight that "proves the credential can
actually push" — and that paragraph was wrong a second way: it said the workflow "logs in with the
default token", while the job logs in with the owner PAT:

```yaml
      - name: Log in to GHCR (owner PAT - can create the org package)
        run: echo "${{ secrets.BUMP_TOKEN }}" | docker login ghcr.io -u "${{ github.repository_owner }}" --password-stdin
```

## The gap

`make check-wiring` already fails on a workflow that calls a `make` target which does not exist — but
only inside a `run:` block: `_workflow_steps()` **strips comment lines**. A target named in the header
comment is invisible to it, so the header drifted with nothing to catch it.

## The fix

- `publish-agent-image.yml`'s `Flow:` now names the real stages.
- `README.md` describes the publish as implemented and says the pre-flight is not implemented (#335).
- `scripts/check_dispatch_forms.py` gains the rule: every `make <target>` in a **stage position** on a
  `Flow:` line or a continuation line must be a Makefile target. Measured before the fix: a naive
  comment scan flags 3 names — the real one plus 2 prose false positives (`pipeline.yml`'s "make
  commands and asserts", "make builds the venv") — so the rule is anchored to stage positions
  (`->` / line start) and skips placeholders (`make ci-<job>`).
- 6 tests in `tests/test_dispatch_forms.py`.

## Verification (real output)

- Negative (the pre-fix workflow, full tree copy): `1 violation(s): publish-agent-image.yml: the
  header's `Flow:` names `make agent-image-push-check`, which is not a target in the Makefile`.
- Positive (this branch): `OK 10 dispatchable workflow(s) …`.
- Rule 6c: `tests/test_dispatch_forms.py` on a pre-fix worktree (`origin/main` + the new test file) →
  **2 failed, 28 passed**; on this branch → **30 passed**.

## Fixes along the way

- `flow_lines()` first read `leading_comment_block()`, which **stops at the `name:` line** — and the
  header block sits *after* `name:` in this repo's workflows, so the rule found nothing. It now scans
  the whole file (the same reason `header_block()` uses a whole-text search).
- The rule is skipped when the tree has no `Makefile` (a scratch fixture), so it cannot produce
  violations it cannot judge.

## Status

Branch `fix/workflow-flow-targets`, PR against `asimov-agent/llgenie:main`. Gates: `make lint`,
`make check-dispatch-forms`, `make openspec-validate NAME=workflow-flow-targets`, `make check-wiring`,
`make check-docs`; the rest of the loop runs in CI.
