# engine-strata-map

## ADDED Requirements

### Requirement: A Strata family without a Hub URL is described, never fatal

The vendoring step SHALL describe every entry of Strata's `FAMILIES` table, including a family that
states no Hub URL, and SHALL mark such a family as not Hub-downloadable instead of raising. A family
that does state a Hub URL SHALL keep the committed file's key order, so the pinned-commit comparison
stays byte-identical.

WHEN a family in Strata's `FAMILIES` table carries no `hf`
THEN `make sync-strata-models` SHALL complete, recording that family with `"hub": false` and no
repo/revision/subdir.

#### Scenario: the family with no Hub URL no longer raises

Given a setup.py whose second family is vendor-hosted and carries no `hf` key
When  the model map is extracted
Then  both families are described and the Hub-less one is marked not Hub-downloadable

- **Test:** `tests/test_strata_missing_hf.py::test_a_family_without_a_hub_url_is_extracted_not_fatal`

#### Scenario: the Hub-hosted family keeps the committed shape

Given a setup.py whose first family states a pinned Hub URL
When  the model map is extracted
Then  its keys are title, repo, revision, subdir, file, shards, experimental — in that order

- **Test:** `tests/test_strata_missing_hf.py::test_a_family_with_a_hub_url_keeps_todays_shape_and_order`

#### Scenario: the committed map is unchanged at the current pin

Given the committed `data/strata_models.json`
When  its families are read
Then  every one is Hub-hosted and none carries the `hub: false` marker

- **Test:** superseded by `openspec/changes/strata-family-shape-invariant` — a snapshot of the v0.1.43 membership red the v0.2.4 bump; `tests/test_strata_missing_hf.py::test_the_committed_map_is_hub_hosted_or_explicitly_not_at_whatever_the_pin_is` locks the shape rule instead

### Requirement: A not-Hub-downloadable family is never planned as a download

The runtime helpers that turn a family into shard paths SHALL refuse or skip a family marked not
Hub-downloadable, and SHALL never build a path from a missing repo.

WHEN a helper is asked about a family with no repo
THEN it SHALL skip it (first-shard map) or raise a named `ValueError` (explicit file request), never a
`KeyError`.

#### Scenario: the first-shard map skips it

Given a vendored map with one Hub family and one Hub-less family
When  the first-shard map is built
Then  only the Hub family contributes an entry

- **Test:** `tests/test_strata_missing_hf.py::test_a_hub_less_family_is_never_mapped_to_a_first_shard`

#### Scenario: an explicit request is refused by name

Given the same vendored map
When  the shard paths of the Hub-less family are requested
Then  a `ValueError` naming "not Hub-downloadable" is raised

- **Test:** `tests/test_strata_missing_hf.py::test_a_hub_less_family_cannot_be_asked_for_its_files`
