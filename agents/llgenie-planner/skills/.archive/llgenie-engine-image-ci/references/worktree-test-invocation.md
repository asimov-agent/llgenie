# Running llgenie tests from a git worktree

## A mount-less docker run in a worktree is NOT a valid red/green

In a worktree the ".git" entry is a FILE whose contents point at the parent
clone. A hand-rolled `docker run ... llgenie/test:latest python -m pytest
tests/...` mounts only the worktree directory, so tests that shell out to `git`
(engine_bump builds real lockfiles, the loader resolves the parent clone) fail
~20+ cases with confusing faults — a FALSE RED, not a regression on your branch.

Rule: run through `make test-unit` (it adds `$(WORKTREE_MOUNT)`, the parent repo
mounted over the worktree path), or replicate the exact flags:

```bash
docker run --rm -u root --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":"$PWD":rw \
  -v "/home/asimov/repository/git/llgenie":"/home/asimov/repository/git/llgenie":rw \
  -w "$PWD" llgenie/test:latest python -m pytest <files>
```

Measured: `tests/test_engine_bump.py` gives 23 failed under the mount-less run and
71 passed with the parent mounted. Before chasing an apparent regression on a
worktree branch, confirm it reproduces with the parent mounted; a failure that
disappears when the parent is mounted was the invocation, not the code.

## A derivation that changes what a step RUNS must also audit its precondition/detect

When a rewriter replaces one install mechanism with another (pip -> release-archive,
curl -> wget), it changes the step's means and must reconcile the *prerequisite* and
*detect* gates for the same resource in the same change. A leftover precondition on
a tool the new steps never call (e.g. `prereqs.common: [uv]` on a curl/tar archive
install) fails `check(mode="native")` with `missing prerequisite: uv` on any host
without that tool — indistinguishable from a genuine requirement, and it survives a
fully green CI because the prereq is only exercised at pick/install time, not by the
unit lane.

When you drop a tool from the steps, drop it from prereqs/detect too, keeping every
tool the steps still use, and add a test that asserts the tool-less host now
succeeds while the legacy mechanism is still refused (the check was narrowed, not
removed).

## Fabricating a tool-less PATH must drop only the offending entries

To simulate "host without uv" a hermetic test replaces PATH with stand-ins for the
tools an install needs and asserts the tool is gone. Do NOT hand PATH a minimal
value like `{stand-ins}:/usr/bin:/bin`: that also drops `/usr/sbin`, where macOS
keeps `sysctl`, so `engine_skills.detect_hardware()` (a step that runs before the
install and is called on darwin) raises `FileNotFoundError: 'sysctl'` — a false red
that only macOS hits while Linux stays green. The assertion "uv is absent" is the
test's real contract; build the PATH so nothing else moves:

- filter the *existing* PATH, keeping every entry that does not provide the tool and
  dropping those that do (`d for d in PATH if not (Path(d)/'uv').exists()`);
- re-add the fake `curl`/`shasum`/`tar` from a separate uv-free directory in front;
- still `assert shutil.which("uv") is None` before running, so a host whose tools
  live somewhere you did not expect fails the test loudly instead of silently
  exercising the pip path you meant to block.
Running the file in the Linux test container proves the logic but not the darwin
`sysctl` path; the macOS CI lane is the only place that half is exercised.
