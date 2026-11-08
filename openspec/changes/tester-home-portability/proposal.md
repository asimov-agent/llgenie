# Convert the tester lane's executed-shell paths from `/home/asimov` to `$HOME`

## What Changes

The tester lane's SOUL/skills reference account-specific absolute paths (`/home/asimov/...`) in
executed-shell instructions. Owner standing rule #2145: use `$HOME` — it resolves in any lane's bash
shell and does not encode a machine account name in a public repository. This change rewrites the 4
executed-shell occurrences in `agents/llgenie-tester/` to `$HOME` and leaves the carve-outs literal.

## Why

A `/home/asimov` path is non-portable and leaks a machine's account name into the tree. `$HOME`
resolves identically in every lane's shell. carve-outs (parsed, not executed) keep the absolute form.

## Expected behavior

- `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md`: worktree path, docker `-v` host mount,
  and redirect target use `$HOME`.
- `references/agent-profile-versioning.md`: `--live-home "$HOME/.hermes/profiles"`.
- No `scripts/*.py`, no systemd/YAML/JSON/crontab value, no other lane's file changed.
- `grep -rn '/home/asimov' agents/llgenie-tester/ | grep -vE '\.py'` → empty.

skip_specs: true — a docs/agent-profile path-only change with no product behaviour to spec-track.
