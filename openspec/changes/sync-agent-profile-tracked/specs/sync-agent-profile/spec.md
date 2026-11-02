# sync-agent-profile

## MODIFIED Requirements

### Requirement: the sync walks Git's tracked files, not the raw directory

`sync-agent-profile` MUST enumerate the files it copies from the set of files **Git tracks** under
`agents/<profile>/` (and, where the tree is a git worktree, read that set with `git ls-files`),
never by walking the raw directory with `rglob`. A file that is untracked and git-ignored (a
`__pycache__/*.pyc`, scratch note, or any other build artifact) MUST NOT be a sync candidate. The
sync MUST therefore never ship a git-ignored file into a live profile and never crash on one.

WHEN the sync (in check or write mode) enumerates the profile's files for a tree that is a git
checkout
THEN every candidate is a git-tracked file under that profile's subtree, and a `__pycache__`/ignored
file is absent from the set.

#### Scenario: `__pycache__` under an `agents/<profile>` dir is not synced

- **Given** an `agents/<profile>` with a git-ignored `scripts/__pycache__/mod.cpython-*.pyc` and a tracked `SOUL.md`
- **When** the sync runs (check or write) for that profile
- **Then** the `.pyc` is absent from the candidate set, `SOUL.md` is the set, and the sync exits 0
- **Test:** `tests/test_agent_profiles.py::test_sync_skips_gitignored_pyc_build_artifacts`

### Requirement: a non-UTF-8 file is a named refusal, never a crash

Reading a candidate file during a sync MUST NOT leak a raw `UnicodeDecodeError`. A file that
`read_text()` cannot decode as UTF-8 MUST be reported as a **named refusal**: a non-zero exit whose
stderr names the file's relative path and states that it is a binary / non-UTF-8 file, so the
operator knows which file and why.

WHEN the sync reads a candidate that is not UTF-8-decodable
THEN the sync exits non-zero and its stderr names that exact file and the binary cause, with no
traceback.

#### Scenario: a tracked non-UTF-8 file reddens the check with its name

- **Given** an `agents/<profile>` containing a file whose bytes are not UTF-8-decodable
- **When** the sync reads that file (check or write)
- **Then** the exit code is non-zero and stderr names the file and says the profile file is binary
- **Test:** `tests/test_agent_profiles.py::test_a_non_utf8_profile_file_is_a_named_refusal_not_a_traceback`
