# 2026-10-12 engine bump destination release

Issue #171, branch `feat/engine-bump-destination-release`.

PR #165 bumped TensorFold `v0.6.5` → `v1.0.7` and left the `git+` pip install.
`bump()` derives before `pin()`, and E10 asked for the tag still in the skill.
`v0.6.5` has no release assets. `v1.0.7` ships the native archives.

The bump now passes the destination tag into derive. An empty release still
keeps pip. A branch bump does not call the release API. The archive rewrite
unpacks the tarball, links the executable to `{prefix}/{version}/bin/{id}`,
and sets `detect` to `{binary} --version`.

The TensorFold skill is not edited here. The next bump from `v0.6.5` is what
writes the archive install. PR #165 as opened still pip-installs `v1.0.7`.

The same run opened #166 llama.cpp-prism (`prism`), #167 strata (`v0.1.43`,
source build) and #168 llama.cpp (`master`). Those installs are not `git+`
pip, so E10 does not rewrite them. `make test-unit` runs one install-kind
case and one matrix case for each of the four engines.
`test_each_failed_bump_engine_keeps_its_install_kind` runs `plan`, `derive`,
`pin` and apply. The GitHub URL is a local git repository. The release body
is a JSON file. The fixture tags are the same shape as the live pins
(`v9.1.0` → `v9.2.0`, `v8.1.0` → `v8.2.0`, branches `master` and `prism`).
Tensorfold's install becomes the archive. Strata keeps clone and cmake and
regenerates `data/strata_models.json`. The two llama.cpp branches request
no release.
`test_each_bump_pr_engine_is_scoped_not_a_placeholder` locks that a pin move
lists that engine, not the placeholder. Two moved pins list both engines. A
README-only change stays the placeholder.

Unhappy cases, same real bump: archives only on the old tag, a tar.gz with
no `.sha256`, a linux archive and no macos archive, already on the highest
tag, a newer `rc` tag, a backward tag, a branch already at tip, and a tag
lookup with no tags.

Top-tier timeouts and #168's unpublished-image install pull stay outside
this change.

The new cases were run here (19 passed). `make test-unit` on the PR is the
full run.
