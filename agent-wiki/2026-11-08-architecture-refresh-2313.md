# docs(architecture): refresh docs/ARCHITECTURE.md for the tree at 20261108T2238 (issue #2313)

**Implements:** issue #2313 — `docs/ARCHITECTURE.md` last described the tree at `12276a3f713e`
(its census line and surface tables carried `measured at <sha>` and reference pointers for a
repository that had since moved on), so a contributor or a reviewing lane read a map that lagged
the code by 9 commit(s) and 38 changed path(s). The architecture bot re-derived the surface and
the drift from real `git` state and rewrote the document; PR #2314 carries that one-file refresh
on `agent/architecture-20261108T2238` as `Asimov Agent <support@docondee.com>`.

## What changed

- **Census line** moved to the current tip: `3886` → `3989` tracked files, and the per-directory
  counts reconciled (`agent-wiki/` 675 → 693, `docs/` 684 → 702, `openspec/` 1544 → 1581,
  `tests/` 278 → 286, `scripts/` 166 → 168) at `measured at 7b8bc3e8be844e40d963452bcc3abc1f604bea13`.
- **Surface tables** now name the drift that landed since the last refresh: `scripts/engine_image.py
  collect` as the build-and-collect form the pin-bump gate rebuilds through (issue #2259); the
  engine-build-pr-trigger `run:` step hoists the base sha and head ref through `env:` instead of
  interpolating `${{ github.* }}` into the shell (issue #2241, run-shell-injection); the
  `registry-liveness` monitor now parses a `NOT PUBLISHED <pin>-<hash>-<variant>` tag out of the
  fleet-gate output and dispatches `engine-build` with `push=true` for each missing cell — a
  partial publish the worker repairs itself (issue #2259, measured torch 2.13→2.14); `rebase_bot`
  and `run-failure-reactor` updated to the repaired registry-liveness failure class; the
  auto-merge `_merge()` refusal-race handling and the verdict `unjudged_reds()` per-workflow
  exemption rules (issues #2236, #2237).
- The document re-describes what the tree actually does today and stays reviewable: a human
  approves the refresh, and the next 6-hour run is quiet until the tree moves again.

## Verified

- `make check-docs` green at the pushed head (this PR's `scope` job) once the note trio below is
  committed — the change→note gate (issue #1123) demands an `agent-wiki/<stem>.md` note, its
  `docs/changes.d/<stem>.md` row and the regenerated `CHANGES.md` index for a `docs/*.md` change.
- The refresh itself is a one-file commit naming this issue and PR #2314.

## Not included

Issue #2258 (the `agents/**` tree earns its own layout row and a reconciling census line) is a
separate gap still open on main: this refresh's census line still enumerates only the named content
directories and leaves the `agents/` tree unnamed — it was not in scope for the bot's drift refresh
and is not closed by this PR.
