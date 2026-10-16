# workflow-flow-targets — a header's `Flow:` must name only targets that exist

## Why

A `workflow_dispatch` workflow's header states the flow of the run, stage by stage
(`# Flow: guard -> make X -> make Y`). Nothing checked that those stages exist.
`publish-agent-image.yml` named `make agent-image-push-check` — a target that is in **no** Makefile —
and `README.md` documented that same target as a real pre-flight that "proves the credential can
actually push".

The README paragraph was wrong twice: the target does not exist, and it claimed the workflow "logs in
with the default token", while the job logs in with the owner PAT (`secrets.BUMP_TOKEN`). A
maintainer reading either file is told about a pipeline that is not the one that runs.

`make check-wiring` already fails on a workflow that calls a `make` target which does not exist — but
only inside a `run:` block. `_workflow_steps()` **strips comment lines**, so a target named in the
header comment is invisible to it. That is the gap.

## What Changes

- **Correct `publish-agent-image.yml`'s `Flow:` line** to the real stages: the guard, then
  `make publish-agent-image` (the "is the hash already on GHCR" decision lives inside
  `scripts/ci_images.py publish`, not in a make target), then `make ci-image-refs`.
- **Correct the README paragraph** to describe the publish as it actually is (hash-tagged,
  owner-PAT login, `make ci-image-refs`), and say plainly that the push pre-flight is **not
  implemented** — tracked as #335.
- **Add the rule** to `scripts/check_dispatch_forms.py`: every `make <target>` in a **stage position**
  on a workflow's `Flow:` line (and its continuation lines) must be a Makefile target. A stage
  position is right after `->` or at the start of the `Flow:` line / a continuation line, so ordinary
  prose ("that decision lives in a make target") is not a finding, and a placeholder (`make
  ci-<job>`) is skipped.
- **Tests** in `tests/test_dispatch_forms.py`: the rule fires on a ghost target and on a continuation
  line, passes on real targets, and does NOT fire on prose or on a placeholder.

## Impact

- `scripts/check_dispatch_forms.py` (the rule) — runs in `ci-unit` via `make check-dispatch-forms`.
- `.github/workflows/publish-agent-image.yml` (one comment), `README.md` (one paragraph).
- `tests/test_dispatch_forms.py` (6 new tests).
- No behaviour change to any job: the publish workflow's steps are untouched.

## Not covered

- **#335** — the pre-flight the README promised (`make agent-image-push-check`): implementing it
  (empty-blob-upload probe before the 60-minute build, in the privileged publish path) is its own
  change with its own tests, filed so this one stays a documentation-and-guard fix.
