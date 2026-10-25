# engine-strata-map

## ADDED Requirements

### Requirement: The committed map states each family's shape, not one pin's contents

A Strata family SHALL be described in exactly one of two shapes, at whatever pin the engine declares:
Hub-hosted (`repo`, `revision` and `subdir` present, and no `hub` key at all) or explicitly not-Hub
(`"hub": false`, and no `repo`/`revision`/`subdir` invented for it). A family SHALL NEVER be both,
and NEVER neither. `subdir` MAY be the empty string (a family published at the repository root — the
committed `swift` is) but MUST be present for a Hub-hosted family.

WHICH families are not-Hub is the pinned `setup.py`'s decision (`nvfp4` carries no `hf` from v0.2.4
on) and SHALL be derived from it — never from a hardcoded list, in the map, in the checker or in a
test. Byte stability against the pin stays `make check-strata-models`' comparison of the regenerated
file with the committed one.

WHEN the family table is checked, by the vendoring step or by a test
THEN every family SHALL satisfy exactly one shape, and a violation SHALL be reported by family name.

#### Scenario: the committed map satisfies the rule at the current pin

Given the committed `data/strata_models.json`
And   the pin the Strata skill declares
When  the family table is checked against the shape rule
Then  no family breaks it, and the map names that pin as its source
And   a map generated at another pin is not accepted as "the invariant"

- **Test:** `tests/test_strata_missing_hf.py::test_the_committed_map_is_hub_hosted_or_explicitly_not_at_whatever_the_pin_is`

#### Scenario: both pins the engine was measured at satisfy the same rule

Given the v0.1.43 family table (every family Hub-hosted) and the v0.2.4 one (`nvfp4` vendor-hosted)
When  each is checked against the shape rule
Then  both pass, because the rule states the shape and not the membership

- **Test:** `tests/test_strata_missing_hf.py::test_the_shape_rule_holds_at_both_pins_that_matter`

#### Scenario: the rule names the defect it exists for

Given a family that is marked not-Hub and still carries a repo, or carries a revision to build a URL
from
And   a family with neither a repo nor the marker, a Hub family carrying `hub: true`, and a Hub family
without a `revision`
When  each table is checked
Then  every one is reported, naming the family and the defect

- **Test:** `tests/test_strata_missing_hf.py::test_the_shape_rule_names_the_defect_it_exists_for`

#### Scenario: the not-Hub set is derived from the setup.py being extracted

Given a `setup.py` whose `FAMILIES` table declares two Hub families and two with no `hf`
When  the map is extracted
Then  the not-Hub set is exactly the families that table declares without an `hf`
And   the extracted table satisfies the shape rule

- **Test:** `tests/test_strata_missing_hf.py::test_the_not_hub_set_is_derived_from_the_setup_py_never_from_a_list`

#### Scenario: check-strata-models names a malformed map

Given a map whose family is marked `hub: false` and still carries its Hub repo
When  `strata_models.py check` runs against it
Then  it fails, naming the family and the defect — not only that the file differs

- **Test:** `tests/test_strata_missing_hf.py::test_check_names_a_malformed_map_instead_of_only_a_diff`

#### Scenario: the live tier derives the set from the fetched pin

Given Strata's `setup.py` at the skill's pinned commit (the live tier fetches it)
When  its `FAMILIES` table and the committed map are compared
Then  the not-Hub set is the same on both sides, and every Hub family's URL is the one the pin states
And   a family the pin declares without `hf` is read as `hub: false`, not crashed on

- **Test:** `tests/test_strata_download.py::test_the_not_hub_set_is_whatever_the_pinned_setup_py_declares`
  and `tests/test_strata_download.py::test_map_tables_equal_setup_py_tables`

## Notes

This requirement supersedes the scenario "the committed map is unchanged at the current pin" of
`openspec/changes/strata-family-without-hub` (issue #416): that scenario asserted the v0.1.43
membership ("none carries the `hub: false` marker") and red the first correct bump that surfaced a
Hub-less family — `nvfp4` at v0.2.4, PR #605. Its `- **Test:**` line now points at the replacement
test, and the byte-stability guard it described lives only in `make check-strata-models`.
