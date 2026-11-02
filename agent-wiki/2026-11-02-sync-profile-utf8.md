# sync-agent-profile: git-tracked view + named non-UTF-8 refusal (issue #1149)

## What changed

`make sync-agent-profile` used to walk the profile directory **filesystem** (`agents/…/*`),
so any untracked or git-ignored artifact under `agents/<profile>/` — `__pycache__/*.pyc`,
scratch notes, `.wasm`, `.sqlite` — was treated as part of the tree, copied into the live
profile, and (when binary) crashed the sync with a bare `UnicodeDecodeError` traceback that
named neither the file nor its cause. Measured on `llgenie-pr-merge-conflict`: a test-side
import dropped a `.pyc` into the tree, the sync choked at `agent_profile_sync.py:135`, and
the gate was red on a crash while the profile was left half-copied. The same root cause had
been silently shipping the `.pyc` into live profiles (file count 18 → 20) for a while,
because the copy could not tell a build artifact from versioned source.

Two independent fixes landed in `scripts/agent_profile_sync.py`:

1. **`profile_files` mirrors git.** The tree is the repository's tree, so the sync now
   enumerates `git ls-files` under `agents/<profile>/` (`.gitignore`-aware) instead of a bare
   `rglob`. Untracked/git-ignored artifacts can no longer reach the live profile at all —
   the filesystem walk remains only as the fallback for non-repository fixture trees in the
   unit tests. This is the `.gitignore`-aware "only tracked text files" acceptance.
2. **No `UnicodeDecodeError` traceback.** Every content read that needs text now goes through
   a safe UTF-8 reader. If a *tracked* file is binary / not valid UTF-8, `write()` refuses it
   **by name** with a distinct exit code (5) — never a traceback — before anything is written.
   `--force` cannot bypass it, because a binary is not a "meaning my overwrite" case, it is a
   file that simply cannot be a profile's text behaviour.

New exit code surfaces: `0` ok, `1` differs after write/`--check`, `2` unknown profile /
missing tree, `3` truncated seed refused, `4` live file edited after the source commit
refused, `5` binary / non-UTF-8 tree file refused.

## Verified

- New unit tests in `tests/test_agent_profiles.py` (git repo fixtures, driving the real
  script via `run_sync`): `profile_files` lists only tracked files; a repo-side `.pyc` is
  never copied and `--check` stays green; a *tracked* non-UTF-8 file is refused naming the
  file with exit 5 and no traceback.
- End-to-end negative control in this worktree: after creating
  `agents/llgenie-planner/__pycache__/evil.pyc` (git-ignored, binary), `write` copied exactly
  the tracked files (107), zero `.pyc` artifacts reached the destination, and a follow-up
  `--check` exited 0.

## References

Issue #1149. Implements `make sync-agent-profile` robustness for untracked/non-UTF-8 files,
so the sanctioned tree → live direction cannot be blocked by one lane's build artifact.
