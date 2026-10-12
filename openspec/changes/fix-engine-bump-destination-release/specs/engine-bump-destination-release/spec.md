## ADDED Requirements

### Requirement: The release lookup uses the destination tag

When a bump derives before it writes the new tag into the skill, E10 MUST request the GitHub release for the destination tag. When no destination tag is passed, E10 MUST request the tag still written in the skill. A destination release with no native archives MUST leave the pip install unchanged and MUST still move the pin. A branch bump MUST NOT request a GitHub release.

The hermetic cases MUST run `plan`, `derive`, `pin` and apply. The skill's GitHub URL MUST be a local git repository. The release body MUST be a JSON file read at the GitHub release URL. Those cases MUST NOT stub `plan`, `load_skills`, `_release_assets`, `_regen_guard` or `_rewrite_pin_asserts`. Tags in the fixture are the `vX.Y.Z` shape of the live bump (`v9.1.0` → `v9.2.0` for the TensorFold `v0.6.5` → `v1.0.7` install, `v8.1.0` → `v8.2.0` for the Strata `v0.1.42` → `v0.1.43` install) so the pin rewrite touches only the fixture tree.

#### Scenario: derive asks for the tag it was given

- **Given** a tag skill whose file still says `v9.1.0`, the shape of TensorFold `v0.6.5`
- **And** only the `v9.2.0` release file publishes checksummed native archives
- **When** derive runs with `ref` `v9.2.0` and clones the local repository behind the skill URL
- **Then** the release request is for `v9.2.0` and `auto.release_assets` lists those archives
- **And** a derive with no `ref` requests `v9.1.0` and sets no `release_assets`
- **Test:** `tests/test_engine_bump.py::test_derive_release_lookup_uses_the_passed_tag`

#### Scenario: each failed bump engine keeps its install kind

- **Given** tensorfold still pinned at `v9.1.0` with a `git+` pip install, strata still pinned at `v8.1.0` with a clone and cmake build, and llama.cpp / llama.cpp-prism still on `master` / `prism` with a cmake build
- **And** the destination tag files publish checksummed native archives
- **When** each engine is bumped through `plan`, `derive`, `pin` and apply
- **Then** tensorfold's release request is `v9.2.0` and its install, `binary` and `detect` are the unpacked executable
- **And** strata's release request is `v8.2.0`, its clone and `cmake_build` lines stay, and `data/strata_models.json` is regenerated
- **And** llama.cpp and llama.cpp-prism request no release and their cmake install stays
- **Test:** `tests/test_engine_bump.py::test_each_failed_bump_engine_keeps_its_install_kind`

#### Scenario: each pin move scopes the matrix to that engine

- **Given** a tree where one of tensorfold, llama.cpp-prism, strata or llama.cpp changes pin and a sibling does not
- **When** the matrix is computed against the parent commit
- **Then** the rows are that engine and not the `engine: none` placeholder
- **And** after the pin is committed, `changed=HEAD` is the placeholder
- **Test:** `tests/test_engine_image_matrix.py::test_each_bump_pr_engine_is_scoped_not_a_placeholder`

#### Scenario: the bump rewrites pip from the destination release

- **Given** a skill pinned at `v9.1.0` whose install is `uv`/`pip` from `git+`
- **And** plan moves it to `v9.2.0`, whose release file has linux-x86_64 and macos-arm64 archives plus a `.sha256` beside each
- **When** the bump runs
- **Then** the only release request is `v9.2.0`
- **And** both backends download, checksum, and unpack that archive
- **And** `binary` is `{prefix}/{version}/bin/{id}` and `detect` is `{binary} --version`
- **And** the pin, `ref`, and the fixture pin asserts move to that sha and tag
- **Test:** `tests/test_engine_bump.py::test_bump_reads_the_destination_release`

#### Scenario: a destination release with no archives keeps pip

- **Given** a tag skill that pip-installs from `git+`
- **And** the destination tag's release has no assets
- **When** the bump runs
- **Then** the release request is for that destination tag
- **And** the pip line and `binary` are unchanged
- **And** the pin and `ref` move
- **Test:** `tests/test_engine_bump.py::test_bump_leaves_pip_when_destination_release_has_no_archives`

#### Scenario: a branch bump does not read a release

- **Given** a branch skill that pip-installs from `git+`, one commit behind its branch
- **And** a release file exists for that branch name
- **When** the bump runs
- **Then** no release is requested and the pip line stays
- **And** the pin moves
- **Test:** `tests/test_engine_bump.py::test_bump_branch_does_not_query_a_release`

#### Scenario: archives on the old tag do not rewrite pip

- **Given** checksummed archives in the old tag's release file and an empty destination release file
- **When** the bump runs
- **Then** the only release request is the destination tag
- **And** the `git+` install stays and the pin moves
- **Test:** `tests/test_engine_bump.py::test_bump_ignores_archives_published_only_on_the_old_tag`

#### Scenario: a missing checksum or a missing backend archive keeps pip

- **Given** a destination archive with no sibling `.sha256`, or a linux archive and no macos archive for a cuda and metal skill
- **When** the bump runs
- **Then** the pin moves and the `git+` install stays
- **Test:** `tests/test_engine_bump.py::test_bump_keeps_pip_when_archive_has_no_checksum`
- **Test:** `tests/test_engine_bump.py::test_bump_keeps_pip_when_a_backend_has_no_archive`

#### Scenario: plan declines a bump that is not a forward stable move

- **Given** a skill already on the highest tag, or a newer `rc` tag, or a skill tag newer than upstream, or a branch pin already at the tip, or an upstream with no tags
- **When** the bump runs
- **Then** an already-current pin, a pre-release, a backward tag, and a branch already at tip change nothing and request no release
- **And** a tag lookup with no tags raises and leaves the pin
- **Test:** `tests/test_engine_bump.py::test_bump_already_at_latest_tag_does_nothing`
- **Test:** `tests/test_engine_bump.py::test_bump_ignores_a_newer_prerelease_tag`
- **Test:** `tests/test_engine_bump.py::test_bump_does_not_move_to_an_older_tag`
- **Test:** `tests/test_engine_bump.py::test_bump_branch_already_at_tip_does_nothing`
- **Test:** `tests/test_engine_bump.py::test_bump_tag_lookup_failure_leaves_the_pin`

### Requirement: The archive install points at the unpacked executable

Applying a native-archive release MUST replace the `git+` install with a checksum-verified unpack of the whole archive, MUST link the one executable in `bin/` to `{prefix}/{version}/bin/{id}`, MUST set `binary` to that path, and MUST set `detect` to `{binary} --version`. The link step MUST NOT use a pipe.

#### Scenario: apply replaces pip, binary, and detect

- **Given** a cuda and metal skill that pip-installs from `git+` and whose `binary` is a bare name
- **And** the release lists checksummed linux-x86_64 and macos-arm64 archives
- **When** the bump applies that release
- **Then** both backends download, checksum, unpack with `--strip-components=1`, and link `bin/{id}`
- **And** `binary` is `{prefix}/{version}/bin/{id}` and `detect` is `{binary} --version`
- **And** no step contains `git+` or `uv`
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_replaces_pip_install`

### Requirement: An unchanged matrix check does not use the bump base

`test_changed_engines_scopes_matrix` MUST treat `HEAD` compared with itself as the placeholder row. It MUST NOT require the checkout to match `origin/main`. A pull request that moves an engine pin changes that engine's image tag, and the matrix for that pull request lists that engine. That scoped result is covered by `tests/test_engine_image_matrix.py::test_matrix_keeps_only_the_engine_whose_pin_changed`.

#### Scenario: the placeholder is HEAD against itself

- **Given** the unit checkout, including a branch whose image tags differ from `origin/main`
- **When** the matrix is computed with `changed=HEAD`
- **Then** the only row is the `engine: none` placeholder
- **And** the full matrix still lists real engines
- **Test:** `tests/test_engine_bump.py::test_changed_engines_scopes_matrix`

#### Scenario: two pin moves list both engines, and a non-image file does not

- **Given** two engine pins moved, or only a file the image tag does not hash
- **When** the matrix is computed against the parent commit
- **Then** both engines are listed when both pins moved
- **And** a README-only change stays the `engine: none` placeholder
- **Test:** `tests/test_engine_image_matrix.py::test_two_moved_pins_list_both_engines`
- **Test:** `tests/test_engine_image_matrix.py::test_a_non_image_file_change_stays_the_placeholder`

#### Scenario: make test-unit selects these cases

- **Given** the `test-unit` recipe
- **When** its pytest `-k` expression is applied
- **Then** the destination-tag cases run, and the three live TensorFold release reads do not
- **Test:** `tests/test_engine_bump.py::test_unit_recipe_runs_the_destination_release_cases`
