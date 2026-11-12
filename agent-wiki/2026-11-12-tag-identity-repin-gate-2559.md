# Tag-identity re-pin gate — a Dockerfile-only retag can no longer merge unpublished (#2559)

Issue: #2559 · branch: feat/tag-identity-repin-gate (PR number recorded when the PR opens)

## What was verified

- **The measured defect.** PR #2517 merged as squash `aa700cf27`: 36 engine Dockerfiles changed,
  zero params files (`git diff aa700cf27^..aa700cf27 -- containers/engines/params/` empty). The
  published tag `<pin8>-<hash8>-<variant>` hashes the Dockerfile + entrypoint.sh + engine_runner.py
  bytes (`engine_skills._image_inputs` via `engine_image._current_tag` / `_tag_at`), so every
  engine x arch tag identity moved; `repinned_engine_ids` diffed the params FILE only, saw nothing,
  the will-arm dispatched nothing, and all 28 committed tags merged unpublished — main went red
  (`linux / unit` run 43149489329: 1 failed / 3629 passed; `registry-liveness` 43149489162: 28/28
  pins unpublished).
- **The fix (one seam).** `scripts/check_engine_pins_published.py` gained `retagged_engine_ids(base,
  root)`: for every buildable cell it compares `ei._tag_at(base, …)` with `ei._current_tag(…)` and
  names the engine when the tags differ (first imports count; disabled cells never move; params
  files that are not engine-shaped are skipped so harness trees cannot poison the union).
  `repinned_engine_ids` now returns the params-file diff UNION that tag-identity diff — the #1622
  params behaviour is never loosened, only extended. Both repin consumers (`engine_build_trigger.py`
  will-arm dispatch, the may-arm merge gate) read the shared function, so the PR that retags an
  image is the PR that dispatches its scoped `engine-build push=true` publish and cannot merge until
  the exact tags resolve.
- **The unit lane.** `tests/test_ci_publish_order.py::_deferred_engines` keeps its three file-text
  heuristics for synthetic harness trees and now unions in `cpp.retagged_engine_ids` against the
  real checkout: the authoritative defer set is the gate's own union. `base == head` moves nothing,
  so a main run still checks every committed tag against the registry (the #2517 self-remediation
  that published the fleet via 28 scoped dispatches stays the safety net, not the only defence).
- **The trigger surface.** `engine-build-pr-trigger.yml`'s `pull_request` `paths` filter narrowed the
  will-arm to `containers/engines/params/**` only — the #2517 Dockerfile-shaped retag never fired the
  will-arm at all. The filter now covers every surface the tag identity hashes
  (`containers/engines/dockerfiles/**`, `containers/engines/entrypoint.sh`, `scripts/engine_runner.py`,
  plus the two scripts that compute the digest, `scripts/engine_skills.py` / `scripts/engine_image.py`),
  so a retagging PR always starts its own scoped `engine-build push=true` builds. `make check-workflows`
  is green over the widened filter, and `make engine-build-pr-trigger-report BASE=origin/main` proves
  hermeticity on a tag-still branch: `[will] 0 repinned engine(s) vs origin/main` — dispatches nothing,
  touches no network.
- **Tests (hermetic, git-only).** Four fixture tests over a real mini git tree (`demo` engine with
  params + Dockerfile.cpu + entrypoint.sh + engine_runner.py): Dockerfile-only change → both diffs
  name it; whitespace-only params edit with unchanged tag → union still names it, tag diff does not;
  tree == base → both empty (probe-free); first import → named once, untouched engine not named.
  A git-only replay test pins main's `d8700c60e` (pre-#2517) as base and proves the deferred set
  contains every engine whose tag identity the merge moved. Targeted suite 58/58 green
  (`tests/test_check_engine_pins_published.py` + `tests/test_ci_publish_order.py` +
  `tests/test_engine_build_trigger.py`); the two live-registry tests are green only once the
  in-flight engine-build dispatch sweep publishes the retagged fleet (verified via CI, not host —
  the host does not build or publish engine images).

## Current status

OpenSpec change `tag-identity-repin-gate` validated; 28 scoped remediation dispatches on main
(0 failures; 12 complete, 16 queued serial at 04:35Z) carry the #2517 fleet to published tags.
The gate change itself ships as the PR closing #2559.
