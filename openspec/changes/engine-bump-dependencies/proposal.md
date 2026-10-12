# feat(engine): bump identifies new pin dependencies

Issue: [#186](https://github.com/asimov-agent/llgenie/issues/186)

## Why

`make engine-bump` regenerates each engine Dockerfile from its skill before the
commit. The generator does not read the new pin. Shared build tools live in the
base image. Packages for one engine are the skill key `apt:`, written inline as
`apt: [name, name]`. There is no `apt-list` file. A name that is not on that key
never reaches that engine's image.

The comparison runs only when both the old sha and the new sha are known. It
reads `requirements.txt`, `pyproject.toml`, and `Dockerfile` with
`git show <sha>:<path>` and keeps names the new pin added. A new apt name is
appended to every existing `apt:` line. No `apt:` line means a hard-fail that
names the packages, and no `container:` block is invented. A new Python
requirement is reported when the install already runs `pip install -r`.
Otherwise the hard-fail names it and no pip line is invented. The pin still
moves and the PR still opens. `dpkg-shlibdeps -O` is the command once a binary
exists; the weekly bump does not compile. A missing detect path that contains
the version is not an installed version.

## What Changes

- `derive` reports python and apt packages added between the old and new sha.
- New apt packages append to an existing `apt:` list, and the generated Dockerfile's `apt-get install` line contains them. No list means a hard-fail and the name stays out of the Dockerfile.
- New python packages the install does not `pip install -r` are a hard-fail.
- The bump PR body includes the dependency line.
- `dpkg-shlibdeps -O` names runtime Debian packages of a binary.
- A missing binary whose path contains the version is not installed.

## Impact

- `scripts/engine_deps.py`
- `scripts/engine_params_derive.py`
- `scripts/engine_bump.py`
- `scripts/engine_skills.py`
- `.github/workflows/engine-bump.yml`
- `containers/test/Dockerfile`
- `tests/test_engine_bump.py`
- `tests/test_engine_bump_pr_body.py`
- `tests/test_engine_skills.py`
- `README.md`

Not this change: issue #170, and the TensorFold tests that still expect `git+`.
