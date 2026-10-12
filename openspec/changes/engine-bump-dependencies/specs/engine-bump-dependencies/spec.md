## ADDED Requirements

### Requirement: A bump reports dependencies the new pin added

`derive` with an old sha MUST read the skill's watched `requirements*.txt`
(not dev or test), `pyproject.toml`, and `Dockerfile` via `git show <sha>:<path>`.
It MUST report packages present at the new sha and absent at the old sha as
`python_added` and `apt_added`.

#### Scenario: a release tag moves from the old tree to the new tree

- **Given** tag `v1.0.0` has `oldpkg`, `staypkg`, `libold1`, and `libstay1`
- **And** tag `v1.1.0` drops `oldpkg` and `libold1` and adds `newpkg` and `libnew1`
- **When** derive runs at `v1.1.0` with the `v1.0.0` sha
- **Then** `python_added` is `newpkg` and `apt_added` is `libnew1`
- **And** `staypkg` and `libstay1` are not added
- **And** the generated Dockerfile installs `libnew1` and does not install `libstay1`
- **Test:** `tests/test_engine_bump.py::test_release_pin_compares_the_old_tag_to_the_new_tag`

#### Scenario: one fixture runs the bump before commit

- **Given** tag `v1.2.0` and tag `v1.3.0` in one git repo
- **And** the new tag adds `new_pkg`, `New_PyDep`, and `libnew1`
- **And** the new tag also has a comment, a pip `-e` line, dev and test requirements, `libalready` already on both `apt:` lines, and `libstay1` on both tags
- **And** the install is `cmake --build`
- **When** `bump` runs and does not commit
- **Then** `hard_fail` names `new-pkg` and `new-pydep`
- **And** both `apt:` lines are `apt: [libold1, libalready, libnew1]`
- **And** the cuda and cpu Dockerfiles install `libnew1` and do not install `libstay1`
- **And** a derive with no old sha reports no dependency delta
- **And** the fixture git HEAD is unchanged
- **Test:** `tests/test_engine_bump.py::test_bump_applies_one_fixture_before_it_commits`

#### Scenario: a requirements file and a Dockerfile gain one package each

- **Given** a real git repo whose new commit adds `newpkg` and `libnew1`
- **When** derive runs at the new sha with the old sha
- **Then** `python_added` is `newpkg` and `apt_added` is `libnew1`
- **Test:** `tests/test_engine_bump.py::test_new_requirements_the_skill_already_installs_are_reported`

### Requirement: Covered python requirements are not a new install line

When the skill install already runs `pip install -r` on a requirements file,
new python names MUST be `python_covered: true` and MUST NOT set `hard_fail`.

#### Scenario: the skill already pip-installs requirements.txt

- **Given** an install step `pip install -r {src}/requirements.txt`
- **When** the new pin adds `newpkg`
- **Then** `hard_fail` is null
- **Test:** `tests/test_engine_bump.py::test_new_requirements_the_skill_already_installs_are_reported`

### Requirement: Uncovered python requirements hard-fail by name

When the install does not pip-install a requirements file, new python names
MUST set `hard_fail` and MUST NOT add a pip line.

#### Scenario: a cmake-only install

- **Given** the install is `cmake --build`
- **When** the new pin adds `newpkg`
- **Then** `hard_fail` contains `newpkg`
- **And** the generated install steps stay `cmake --build` and do not name `newpkg`
- **Test:** `tests/test_engine_bump.py::test_new_requirements_the_skill_does_not_install_hard_fail`

### Requirement: New apt packages land on an existing apt list

The skill key is `apt:`, written inline as `apt: [name, name]`. There is no
`apt-list` file. `generate-engine-params` copies that key into that engine's
Dockerfile and does not put the name in the shared base.

New apt packages MUST be `auto.apt_add` when the skill already has an `apt:`
line, and `_apply_findings` MUST append them to every front-matter `apt: [...]`
line. With no `apt:` line, `hard_fail` MUST name them and no container block
is created. The comparison runs only when the old sha and the new sha are both
known.

#### Scenario: the skill lists apt packages

- **Given** `apt: [libold1]`
- **When** the new Dockerfile adds `libnew1`
- **Then** the skill text contains `apt: [libold1, libnew1]`
- **And** `render_dockerfile` contains `libnew1` on an `apt-get install` line
- **And** the shared base Dockerfile does not contain `libnew1`
- **And** the generated install steps still `pip install -r` `requirements.txt` and do not name `newpkg`
- **Test:** `tests/test_engine_bump.py::test_new_requirements_the_skill_already_installs_are_reported`

#### Scenario: the skill has no apt list

- **Given** no `apt:` key
- **When** the new Dockerfile adds `libnew1`
- **Then** `hard_fail` contains `libnew1` and `apt_add` is absent
- **And** the generated Dockerfile and the shared base do not contain `libnew1`
- **Test:** `tests/test_engine_bump.py::test_new_apt_package_without_an_apt_list_hard_fails`

### Requirement: dpkg-shlibdeps names runtime packages

`shlib_packages` MUST run `dpkg-shlibdeps -O` on the binary and return the
Debian package names, including `libc6` for a normal C binary, when that
tool is installed. The Linux unit container installs `gcc` and `dpkg-dev`
for this test and MUST then return `libc6`. The published test image is
unchanged. A host that cannot install the tool MUST raise `RuntimeError`
naming `dpkg-shlibdeps`. The test runs on both hosts. It does not skip.

#### Scenario: a binary compiled in the test

- **Given** `gcc` produced a binary
- **When** `dpkg-shlibdeps -O` reads it
- **Then** the names include `libc6`
- **Test:** `tests/test_engine_bump.py::test_dpkg_shlibdeps_names_libc`

### Requirement: A version in a missing path is not installed

`_detect_run` MUST ignore a `No such file or directory` line. A command that
prints a version and exits non-zero MUST still count as installed.

#### Scenario: the archive detect path contains the version

- **Given** `{prefix}/1.0.7/bin/tensorfold` does not exist
- **When** native status runs that detect command
- **Then** the state is `missing`
- **Test:** `tests/test_engine_skills.py::test_missing_binary_whose_path_contains_the_version_is_missing`

### Requirement: The bump PR body names the new dependencies

When the bump prints `[engine-bump] DEPS ...`, the PR body MUST contain that
line after the base body.

#### Scenario: python and apt packages were added

- **Given** `DEPS=python_added=newpkg apt_added=libnew1`
- **When** the workflow renders the body
- **Then** the body ends with `- **Dependencies:** python_added=newpkg apt_added=libnew1`
- **Test:** `tests/test_engine_bump_pr_body.py::test_dependency_line_is_appended`
