# Engine bump dependencies

Issue #186. Before the bump commits, `derive` reads the new pin's
`requirements.txt`, `pyproject.toml`, and `Dockerfile` with `git show`. New apt
packages append to an existing `apt:` list so `generate-engine-params` writes
them into that engine's Dockerfile. New python packages the skill already
`pip install -r` are reported. Otherwise the bump hard-fails with the names.
`dpkg-shlibdeps -O` names runtime libraries of a binary. A missing detect path
that contains the version is not installed.

The skill key is `apt:`, written `apt: [name, name]`. There is no `apt-list`
file. The why, when, and what are in `AGENTS.md` under "Engine bump
dependencies", and in issue #186 and PR #187.

The unit test follows the new apt name through `generate_params` and
`render_dockerfile` and checks the `apt-get install` line. A hard-fail leaves
the name out of that Dockerfile and out of the install steps. A release pin
compares the tagged old tree to the tagged new tree. One fixture of the old
tag and the new tag runs `bump` through pin and apply, renders both
Dockerfiles, and does not commit.
