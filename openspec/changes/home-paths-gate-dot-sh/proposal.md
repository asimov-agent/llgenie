# home-paths-gate-dot-sh

## Why

Issue #2145 made `$HOME` the required form in every authored text and `check_agent_profiles.py`
scans `agents/**/*.md` for literal home paths — but executed shell lines in `agents/**/*.sh` were
outside the scan, so `stack-replay.sh` (llgenie-pr-merge-conflict's lane script) still embedded a
hard-coded `/home/<user>` fallback that silently breaks on any other host. A rule enforced only in
prose is a rule the next shell script can break (issue #2436).

## What Changes

- `scripts/check_agent_profiles.py`: extend the home-path-literal scan from `agents/**/*.md` to
  `agents/**/*.sh` too. A line whose first non-blank character is `#` is skipped (a comment
  recounting a past defect keeps its absolute path — `skill-script-hygiene.md`; a comment is not
  shipped behaviour). `scripts/*.py` stays excluded on purpose (a Python literal needs a real path
  or `pathlib.Path.home()`).
- `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/stack-replay.sh`: the fallback
  home path becomes `$HOME`-based, so the replay works on every lane host.
- `tests/test_home_paths_gate.py`: new scenarios — a literal executed line in a `.sh` goes red, a
  commented absolute path stays accepted, `.md` coverage unchanged.

## Impact

- Affected: `scripts/check_agent_profiles.py`, `tests/test_home_paths_gate.py`, the rebase lane's `stack-replay.sh`.
- Closes GitHub issue #2436 (PR #2441 carries the implementation this change records).
