# fix(engine): bump reads the destination tag when a release drops pip

Issue: [#171](https://github.com/asimov-agent/llgenie/issues/171)

## Why

PR #165 (`v0.6.5` → `v1.0.7`) failed `engine-image-tensorfold-cuda`. The image
still pip-installs `tensorfold @ git+…@v1.0.7`, and TensorFold 1.0+ refuses
that build. #152 added the archive rewrite, and that commit is an ancestor of
the bump. The bump job logged `applied: none` and `auto: {}`.

`bump()` calls `derive()` before `pin()`. The release lookup used `skill["ref"]`,
which was still `v0.6.5`. That release has no assets, so the pip install stayed.
`v1.0.7` ships `tensorfold-1.0.7-linux-x86_64.tar.gz` and
`tensorfold-1.0.7-macos-arm64.tar.gz`, each with a sibling `.sha256`.

## What Changes

- E10 reads the destination tag passed by the bump, which is the tag being
  moved to. With no destination tag it still reads the tag in the skill.
- A tag bump whose new release has no native archives still moves the pin and
  leaves the pip install.
- A branch bump does not request a GitHub release.
- The archive rewrite unpacks the whole archive, links the one executable in
  `bin/` to `{prefix}/{version}/bin/{id}`, sets `binary` to that path, and sets
  `detect` to `{binary} --version`.
- This PR does not edit the TensorFold skill. The next bump from `v0.6.5`
  applies the rewrite. PR #165 as opened still pip-installs `v1.0.7`.
- The same bump run opened #166 (llama.cpp-prism, branch `prism`), #167
  (strata, tag `v0.1.43`, source build) and #168 (llama.cpp, branch `master`).
  None of those skills pip-install the engine from `git+`, so E10 does not
  rewrite them. All four PRs failed `linux / unit` on
  `test_changed_engines_scopes_matrix`, which required this checkout to match
  `origin/main`. A bump PR's pin move is a real tag change. The unchanged
  case is `HEAD` against itself.
- `make test-unit` has one install-kind case and one matrix case for each
  of those four engines, so that run cannot go red the same way again.
  The install-kind cases run `plan`, `derive`, `pin` and apply. The skill
  URL is a local git repository and the release body is a JSON file.
  Unhappy cases cover an old-tag archive, a missing checksum, a missing
  backend archive, an already-current pin, a pre-release, a backward tag,
  a branch already at tip, and a failed tag lookup.
- `AGENTS.md` forbids mocking business logic. A test of that logic runs
  it. Only an external call may be stood in, and an end-to-end test does
  not stand that call in either.
- Not this change: #165/#167/#168 `top-tier` timeouts, the vllm dry-run
  timeout on #165 and #168, and #168's install pull of an unpublished
  llama.cpp tag (issue #170).

## Impact

- `scripts/engine_bump.py`, `scripts/engine_params_derive.py`, `scripts/engine_skills.py` (`load_skills` reads `SKILLS_DIR` at call time)
- `tests/test_engine_bump.py`, `tests/test_engine_image_matrix.py`
- `README.md`
