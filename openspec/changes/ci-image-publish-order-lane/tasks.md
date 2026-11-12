# Tasks

## scripts/ci_images.py

- [x] 1.1 Factor `ensure`'s local build into `_build_local(name, root)`; `ensure` keeps identical behavior.
- [x] 1.2 `pull` defers when the pull fails AND `published(r)` confirms the tag is absent AND
      `GITHUB_EVENT_NAME == "pull_request"`: `::warning title=publish deferred::` line naming the
      landing publish (issue #2518), local build via `_build_local`, exit 0; hard failure kept
      otherwise (push runs and published-tag-but-failed-pull).

## Makefile wording

- [x] 2.1 `test-image-pull` comment and the `ci-<job>` seam comment state the event scope (push
      fails, `pull_request` defers to a local build, issues #155/#1673/#2518). No target body change.

## tests/test_ci_images.py

- [x] 3.1 `_fake_docker` scrubs inherited `GITHUB_EVENT_NAME` and gains a `pull_fail` knob
      (published tag + failing pull).
- [x] 3.2 PR deferral test: missing tag + `pull_request` → exit 0, deferral line with #2518, local
      `build -t llgenie/test:latest`, no `buildx build`, temp context removed.
- [x] 3.3 PR pull test: published tag + `pull_request` → pull+tag only, no build, no deferral line.
- [x] 3.4 Push hard-fail test: missing tag + `push` → exit 1, never-build stderr, no build.
- [x] 3.5 Published-tag-but-failed-pull test: `pull_request` + `pull_fail` → exit 1, no build.

## Verification

- [x] 4.1 Targeted pytest `tests/test_ci_images.py` rc=0 (whole file, existing tests unchanged):
      proven: `pytest tests/test_ci_images.py -q` → `40 passed in 4.34s`, rc=0 (2026-11-12).
- [x] 4.2 `make openspec-validate NAME=ci-image-publish-order-lane` rc=0: proven —
      `Change 'ci-image-publish-order-lane' is valid`, rc=0 (2026-11-12).
- [x] 4.3 `make check-wiring` and `make check-workflows` rc=0 (no workflow file changed): proven —
      wiring `OK 419 documents … 373 make targets` rc=0; workflows `OK` rc=0 (2026-11-12).
      Consumer sweep (12 modules importing `ci_images`): 381 passed; 1 pre-existing failure
      `test_every_image_install_pulls_is_published` — reproduced identically on a detached
      `origin/main` worktree (fleet dispatches pending on GHCR; fixed by PR #2562's dispatch
      contract + the engine-build sweep, #2529), unrelated to this change's files.
- [x] 4.4 Issue #2518 body synced to this design (AGENTS sync-back) and the fork-head live-proof
      follow-up issue filed and cross-linked: proven — issue #2518 patched (readback: marker first
      line `true`, contains `#2563` `true`, unticked `- [ ]` present `false`, 3 ticked AC with proven
      stamps citing commit `4f807d428`); follow-up issue #2563 filed via `issue_body.render`
      (USER 1000:1000 fold + fork-head live proof, links back to #2518), 2026-11-12.
- [x] 4.5 `agent-wiki/` entry + `docs/changes.d/` row naming issue #2518 and the PR: entries
      written naming issue #2518 + #2563; PR number added to the wiki line as soon as the PR opens.
- [x] 4.6 PR staging verified: branch carries the implementation + tick commits; staged PR body
      (#2564) carries umbrella-aware close handling — no closing keyword to #2518 (its lanes
      #2504, #2529, #2563 are open), ticked AC with `proven:` evidence and `Not covered` naming
      #2563; `make bot-stamp-body` rc=0 (AGENTS/BASE pair on the body, 2026-11-12); local
      `check_pr_acceptance.py` and `check_pr_closing.py` rc=0 against head `6d7269378` and this
      body. Push + PR-open proofs are recorded in the wiki entry.
