# Execution traps in this repo (worktrees, container ownership, host-branched gates)

Read this before the first edit of any llgenie change. Each trap silently wastes a whole tree or a
whole CI run, and each has a concrete check.

## 1. Absolute paths, always

The `execute_code` kernel keeps its OWN working directory. It does **not** follow a `cd` that was run
in `terminal`, so a relative path written from the kernel lands in whatever directory the session
started in — for this repo, the user's main checkout — and not in `../llgenie-wt/<kebab>`.

```python
WT = pathlib.Path("/home/<user>/repository/git/llgenie-wt/<kebab>")   # bind it once
for p in sorted((WT / ".github/workflows").glob("*.yml")):          # every path from WT
    ...
```

- `terminal` with `workdir=` and `patch`/`write_file` with an absolute path are safe.
- If it already happened: the user's checkout shows the edits in `git status`; revert with
  `git checkout -- <paths>` there (never leave them), then re-apply in the worktree.
- Cross-tree copies are also a trap: a file you "already have" in the main checkout is at a
  different commit than `origin/main` — read it from the worktree.

## 2. The OpenSpec CLI leaves its change directory root-owned

`make openspec-new NAME=<name>` runs the CLI inside its container as root, so
`openspec/changes/<name>/` is owned by root and the first `write_file` into it answers
`Permission denied`. `sudo` may demand a password the session does not have.

```bash
WT=/home/<user>/repository/git/llgenie-wt/<kebab>
docker run --rm -v "$WT":/w -w /w llgenie/test:latest \
  chown -R "$(id -u):$(id -g)" openspec/changes/<name>
```

Do it immediately after `make openspec-new`, before writing `proposal.md` / `specs/**/spec.md` /
`tasks.md`. The same chown applies to any scratch directory a containerised recipe writes into.

## 3. A gate test that asserts the CONTAINER shape is a Linux-only test

`TEST_RUN`, `TEST_OPTS`, `ENGINE_TEST_RUN` and `CI_HOME_CLEAN` branch on `HOST_OS` (`uname -s`):

- Linux → `$(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)`, i.e. `-v "<checkout>":/repo:rw` and
  `llgenie/test:latest`;
- Darwin → the native 3.11 venv (`test -x "$(VENV)/bin/python" … && env PATH=… python …`), no
  volume and no image at all.

So a test asserting `-v "<checkout>":/repo:rw` in `make -n <target>` passes `linux / unit` and can
never pass `macos / unit`. Write it in two layers:

1. the invariant both hosts resolve — read the make VARIABLE, not the recipe:
   `make -p -n <target>` prints `TEST_OPTS := …` / `ROOT := …` / `REPO = …`, and that is the value
   the gate actually mounts;
2. the recipe against the shape its host expands — `platform.system() != "Darwin"` picks
   container-shape vs venv-shape, and the macOS branch asserts the absence of `-v ` and of the image
   name, plus the presence of the script it runs.

Mirror the two layers in the OpenSpec spec as two scenarios, each with its own `- **Test:**` line so
the macOS branch is visibly pinned by the `macos / unit` job.

## 4. Expanding the other host's branch without that host

`HOST_OS := $(shell uname -s)` overrides an environment variable, so `HOST_OS=Darwin make -n lint` is
silently ignored. `make -e HOST_OS=Darwin -n <target>` is the way to see what macOS would run. Use it
to prove the old assertion fails there and the new one passes before pushing.

## 5. Slicing workflow YAML: anchor on the FULL step name

A target that is a prefix of another breaks a text slice — `wf.split("make auto-merge")[1]` also cuts
at `make auto-merge-resolve`, so the assertion reads a truncated step and fails for a reason that is
not the rule being tested. Anchor on the whole `- name: …` line (or on a phrase unique to that step).
The same applies to `split("make test")` vs `make test-unit`, `make ci-unit` vs `make ci-unit-run`.

## 6. Proving a red is not yours

Before touching anything on a red PR: `git diff --name-only origin/main` on the branch, then run the
failing test locally on that same branch. Two PRs reddening on the same test at the same minute, or
both OS jobs of one PR, while the diff names none of that code, is upstream/live-data drift — file it
as its own issue quoting the upstream value (an exact Hub filename, a measured t/s) instead of
loosening the assertion in the PR you are holding.
