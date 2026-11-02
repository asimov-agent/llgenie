# Make sync-agent-profile Git-tracked-file-aware and binary-safe

## Why

`make sync-agent-profile` copies **every file** under `agents/<profile>/` into the live profile,
including untracked, non-UTF-8 build artifacts (`.pyc`, scratch notes, wasm, sqlite), and crashes
with a raw `UnicodeDecodeError` when it hits one — blocking the sanctioned tree → live direction for
a whole lane (issue #1149).

Measured tonight on `llgenie-pr-merge-conflict`:

1. A repo-side test imports `agents/.../scripts/salvage-four-bucket.py`, which writes
   `scripts/__pycache__/*.pyc` into the tree. Those files are git-ignored, so no review or gate sees
   them, but `make sync-agent-profile PROFILE=<name>` walks the profile directory **filesystem**
   (`path.rglob("*")`, not `git ls-files`), hits the `.pyc`, and dies:

   ```
   File ".../scripts/agent_profile_sync.py", line 135, in shrinks
       tree_text, live_text = path.read_text(), target.read_text()
   UnicodeDecodeError: 'utf-8' codec can't decode byte 0x7f in position 0: invalid start byte
   ```

   Result: the gate is red on a crash, not on a content diff, and the profile is left half-copied.

2. Downstream of the same root cause, sync had silently shipped `.pyc` into the live profile the
   whole time (file count 18 → 20), because it copies untracked files and cannot tell a build
   artifact from a versioned source.

## What Changes

- **`scripts/agent_profile_sync.py`** — the filesystem walk that enumerates "the files the tree
  carries" (`profile_files()`) stops reading the raw directory and mirrors **Git's tracked-file
  view**: it runs `git ls-files` against the profile subtree (when the tree is a git checkout) and
  skips git-ignored/untracked files entirely; and every `read_text()` guard wraps the
  `UnicodeDecodeError` so a genuinely non-UTF-8 file is a **named refusal**, not a traceback.

- **Sync scope** becomes `.gitignore`-aware: only files Git tracks under `agents/<profile>/` are
  candidates for copy/check, so a stray `.pyc` from any lane can never be shipped into a live
  profile and never reddens the gate.

- **Tests** reproduce both directions: a `__pycache__/*.pyc` created under `agents/` does not
  appear in the sync set, and a non-UTF-8 file under a profile dir produces a named non-zero
  refusal instead of a `UnicodeDecodeError` traceback.

## Acceptance

- `make sync-agent-profile PROFILE=<any> CHECK=1` (and the write path) works after a
  grep-import creates `__pycache__` under an `agents/` dir — exit 0, no crash.
- A non-UTF-8 file under a profile dir produces a named-file refusal (non-zero exit, stderr names
  the file and that it is binary), never a traceback.
- `sync-agent-profile` syncs only tracked files (`.gitignore`-aware); a git-ignored untracked file
  is never copied.
- `make test-unit` green; `make openspec-validate NAME=sync-agent-profile-tracked` exits 0.
