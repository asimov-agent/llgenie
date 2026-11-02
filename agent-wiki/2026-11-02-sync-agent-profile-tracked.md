# sync-agent-profile is Git-tracked-file-aware and refuses non-UTF-8 by name

Issue: [#1149](https://github.com/asimov-agent/llgenie/issues/1149) — PR: [#1545](https://github.com/asimov-agent/llgenie/pull/1545)

## Why

`make sync-agent-profile` copied **every file** under `agents/<profile>/` into the live profile,
including untracked, non-UTF-8 build artifacts (`.pyc`, scratch notes, wasm, sqlite), and crashed
with a raw `UnicodeDecodeError` when it hit one — blocking the sanctioned tree → live direction for
a whole lane. Measured on `llgenie-pr-merge-conflict`: a repo-side test imported a script, which
wrote `scripts/__pycache__/*.pyc` into the tree; the sync walked the raw directory, hit the `.pyc`,
and died on a traceback that named neither the file nor the cause. Downstream, sync had silently
shipped `.pyc` into the live profile (file count 18 → 20) because it could not tell a build
artifact from a versioned source.

## What changed

- **`scripts/agent_profile_sync.py`** — `profile_files()` now mirrors **Git's tracked-file view**:
  when the tree is a git worktree it reads `git ls-files` for the profile subtree, so a
  git-ignored/untracked artifact (`__pycache__/*.pyc`, a scratch note) is never a sync candidate;
  a non-git `--root` fixture falls back to the directory walk but skips the same ignored
  directories. Every `read_text()` is guarded (`_read_text`), and `check()`/`write()` refuse a
  candidate that is not UTF-8-decodable with a **named** non-zero refusal (stderr names the file
  and that it is binary), never a `UnicodeDecodeError` traceback.

- **Tests** — `test_sync_skips_gitignored_pyc_build_artifacts` (a git-ignored `.pyc` under
  `agents/<profile>` is absent from the candidate set and the sync exits 0 without shipping it) and
  `test_a_non_utf8_profile_file_is_a_named_refusal_not_a_traceback` (both `check` and `write` exit
  5 and name the file).

## Acceptance

- `make sync-agent-profile PROFILE=<any> CHECK=1` (and the write path) works after a grep/import
  creates `__pycache__` under an `agents/` dir — exit 0, no crash.
- A non-UTF-8 file under a profile dir produces a named-file refusal (non-zero exit, stderr names
  the file and that it is binary), never a traceback.
- `sync-agent-profile` syncs only tracked files (`.gitignore`-aware); a git-ignored untracked file
  is never copied.
