# tag-identity-repin-gate

## ADDED Requirements

### Requirement: the repin set includes engines whose image tag differs from base (tag-identity diff)

`check_engine_pins_published.retagged_engine_ids(base)` MUST name every engine whose published
image tag `<pin8>-<hash8>-<variant>` this tree would publish differs from the tag `base` would
publish, for every buildable engine×arch cell (the full committed matrix minus DISABLED). The
comparison MUST use the one tag formula (`engine_skills._image_inputs`, hashing the params file +
`Dockerfile.<variant>` + `entrypoint.sh` + `engine_runner.py`), via `ei._current_tag` (this tree)
vs `ei._tag_at(base)` (the base). An engine with no base copy (a first import) MUST count too.
`retagged_engine_ids` on a tree identical to its base (base == head) names nothing.
`repinned_engine_ids(base)` MUST be the union of the params-FILE diff (unchanged behaviour) and
`retagged_engine_ids` — never a loosening of the existing params diff.

WHEN a change re-tags an engine's image (e.g. its Dockerfile bytes moved while its params file
did not) OR a params file moved
THEN `repinned_engine_ids` names that engine, so the may-arm merge gate and the will-arm
publisher both see it as a repin

#### Scenario: a Dockerfile-only change re-tags the engine and is named by tag-identity

- **Given** a synthetic engine repo whose variant Dockerfile changed while its params file did not
- **When** `retagged_engine_ids("main", root)` runs on that working tree
- **Then** it names that engine (its computed tag differs from base's)
- **Test:** `tests/test_check_engine_pins_published.py::test_retagged_engine_ids_names_an_engine_whose_dockerfile_changed_while_params_did_not`

#### Scenario: a tree identical to its base retags nothing

- **Given** a synthetic engine repo whose working tree equals its base commit
- **When** `retagged_engine_ids("main", root)` runs
- **Then** it names no engine
- **Test:** `tests/test_check_engine_pins_published.py::test_retagged_engine_ids_names_nothing_when_base_equals_head`

#### Scenario: the repin set is the union of the params diff and the tag-identity diff

- **Given** a synthetic engine repo whose Dockerfile changed (params byte-identical)
- **When** `repinned_engine_ids("main", root)` runs
- **Then** it names that engine via the tag-identity half of the union
- **Test:** `tests/test_check_engine_pins_published.py::test_repinned_engine_ids_is_the_union_of_params_and_tag_identity`

### Requirement: the will-arm publisher dispatches scoped push=true for a tag-retagged engine

`engine_build_trigger` MUST inherit the union through `repinned_engine_ids`: an engine that a
change only re-tags (empty params diff) is a repin to the trigger, and the trigger MUST dispatch
a scoped `engine-build push=true engine=<id>` run for it and await that run's verdict. A change
that retags nothing dispatches nothing (hermetic).

WHEN the will-arm runs on a change that re-tags an engine
THEN it dispatches a scoped `push=true` engine-build for exactly that engine and passes only when
that run concludes success

#### Scenario: a tag-retagged engine gets a scoped push=true dispatch

- **Given** a retagged engine named by the shared union
- **When** the will-arm check runs
- **Then** it dispatches `engine-build push=true engine=demo` and awaits the verdict
- **Test:** `tests/test_engine_build_trigger.py::test_a_tag_retagged_engine_dispatches_scoped_push_true`

### Requirement: the unit deferral computes the deferred set from the shared tag-identity helper

`tests/test_ci_publish_order.py::_deferred_engines` MUST defer an engine whose tag this tree
re-tags via the SAME `retagged_engine_ids` helper the may-arm uses (not a hand-rolled text scan):
a retagging PR defers retagged engines to `make ci-wait-engine-images`, and a base==head run
(every retag already published by the PR that merged it) defers nothing, so every tag is still
registry-checked.

WHEN the deferred set is computed for a change that re-tags an engine
THEN that engine is deferred (not required from the registry)

#### Scenario: a Dockerfile-only change defers that engine via the shared helper

- **Given** a synthetic engine repo whose Dockerfile changed on a branch (base stays at main)
- **When** `_deferred_engines(params_dir=…, base="main")` runs
- **Then** that engine is deferred to its producer publish
- **Test:** `tests/test_ci_publish_order.py::test_a_dockerfile_only_change_is_deferred_via_the_shared_helper_and_base_eq_head_is_not`

#### Scenario: base equals head defers nothing on the shared helper

- **Given** a synthetic engine repo whose working tree equals its base (base == head)
- **When** `_deferred_engines(params_dir=…, base="main")` runs
- **Then** nothing is deferred
- **Test:** `tests/test_ci_publish_order.py::test_a_dockerfile_only_change_is_deferred_via_the_shared_helper_and_base_eq_head_is_not`
