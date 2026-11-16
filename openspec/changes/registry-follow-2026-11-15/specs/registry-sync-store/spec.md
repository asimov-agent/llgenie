# registry-sync-store — spec delta

## ADDED Requirements

### Requirement: A store that moves is followed from a green additive check

WHEN upstream `master` publishes a newer trending store AND `make sync-registry` +
`make check-registry` + `make check-registry-keys` are green on the vendored result THEN a sync
PR carrying that store SHALL exist so the weekly lane stops re-failing against the stale vendored
copy.

#### Scenario: the 2026-11-15 store is vendored green

- **Given** the vendored `2026-11-04T15:29:04Z` store (117 models) on `main`
- **And** upstream `master` publishing `2026-11-15T08:29:53Z` (118 models)
- **When** the follow sync runs and both registry gates run on the result
- **Then** both gates exit 0 and the follow PR is open against `main`
- **Test:** `tests/test_registry_keys.py::test_the_vendored_store_is_additive_against_itself`
  (live pair) and the PR-measured gate rc on the synced tree

### Requirement: Retention-pruned posts are rehydrated at the vendor seam, never widened away

`make sync-registry` SHALL carry `engagement.seen_posts` posts that upstream's 30-day retention
(`update_trending.py::prune_posts`, `RETENTION_DAYS = 30`) removed from the new store back from
the previous vendored copy of `data/models.json`, keyed by `/status/<id>` post identity: a
fresher entry for the same post wins over the carried one; a post the new store re-attributed to
another surviving model row is not carried a second time; a carried entry is appended to the
surviving row that previously held it. A model row that the new store no longer carries SHALL
NOT be resurrected by the rehydrate — its removal stays a guard failure. The guard
`scripts/registry_keys.py` SHALL NOT gain an exemption, vocabulary entry or scan change for this
class.

WHEN the sync vendors a store whose only losses are retention-pruned `seen_posts` posts THEN the
vendored result contains every previously tracked post and `make check-registry-keys` exits 0.

#### Scenario: a retention-pruned post survives in the vendored ledger

- **Given** a vendored row whose `engagement.seen_posts` carries a real-URL post dated beyond
  the 30-day window
- **And** a new store whose same row dropped that entry
- **When** the sync writes the vendored file
- **Then** the post is present in that row's `seen_posts` and the additive guard exits 0
- **Test:** `tests/test_registry_seen_posts_rehydration.py::test_retention_pruned_posts_are_carried_from_the_previous_vendored_copy`

#### Scenario: the fresher entry for the same post wins

- **Given** a previous vendored post entry with counters `(likes 10)`
- **And** a new store carrying the same `/status/<id>` with `(likes 20)`
- **When** the sync writes the vendored file
- **Then** the row carries only the `(likes 20)` entry for that post
- **Test:** `tests/test_registry_seen_posts_rehydration.py::test_a_fresher_entry_for_the_same_post_wins`

#### Scenario: a re-attributed post is not carried twice

- **Given** a previous vendored post on model row `a`
- **And** a new store where the same post now lives on model row `b`
- **When** the sync writes the vendored file
- **Then** the post appears exactly once across the store
- **Test:** `tests/test_registry_seen_posts_rehydration.py::test_a_post_reattributed_to_another_row_is_not_carried_twice`

#### Scenario: a gone model row stays a guard failure

- **Given** a previous vendored row `gone-model` carrying tracked posts
- **And** a new store with no `gone-model` row
- **When** the sync writes the vendored file
- **Then** no row was created for `gone-model` and the additive guard exits 1 naming the model
- **Test:** `tests/test_registry_seen_posts_rehydration.py::test_a_removed_model_row_is_never_resurrected_by_the_rehydrate`

#### Scenario: placeholder posts are not carried

- **Given** a previous vendored row whose `seen_posts` holds a placeholder entry (no
  `/status/<id>`)
- **And** a new store whose row dropped it
- **When** the sync writes the vendored file
- **Then** the placeholder is absent — placeholders are derived state, rebuilt from measurements
- **Test:** `tests/test_registry_seen_posts_rehydration.py::test_placeholder_posts_are_never_carried`
