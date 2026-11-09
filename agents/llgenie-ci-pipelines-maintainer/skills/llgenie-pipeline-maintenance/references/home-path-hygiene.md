# Documenting paths: `$HOME`, never `/home/<user>`

Every doc this lane authors — SOUL, skill `SKILL.md`, `references/`, repo markdown, PR bodies — writes `$HOME`, never a literal `/home/<user>` path. A literal path is wrong on every machine but this one and leaks a username.

## Procedure (profile skills)

1. Measure before editing: `grep -rl '/home/'$USER '$PROFILE/skills' --include=*.md` (and SOUL.md). Count lines, not just files.
2. Convert only the shell-executable occurrences. A line whose path is consumed by a shell (`sudo pacman -U $HOME/...`, `git worktree remove $HOME/...`, `docker run -v $HOME/...`) takes `$HOME` — the shell expands it.
3. Re-measure and report the before/after count per scope (SOUL / active skills / archive), plus every line deliberately left absolute and WHY.

## Carve-outs — leave these ABSOLUTE

These are the paths where `$HOME` would silently break, so they must stay literal:

- **Python-evalled strings.** `json.load(open("/home/<user>/.hermes/auth.json"))`, and `export K="$(python3 -c 'import json;print(json.load(open("/home/<user>/...")))'...)"` — inside a single-quoted Python literal nothing expands `$HOME`, so converting produces a path that fails at runtime. Leave absolute; the whole `python3 -c '...'` line is one carve-out even though it looks like shell.
- **`scripts/*.py`.** Script source paths are code, not docs; leave them.
- **Parsed config** — systemd unit fields, YAML/JSON values — a reader of the file, not a shell, resolves the path.

## Pitfall: the sync gate re-introduces the literal

The repo tree copy of a profile still holds the literal until the tree itself is swept, so running `make sync-agent-profile` from the tree would copy the literal BACK over the cleaned live profile. Do the live-profile sweep against the tree state you have; the tree-wide sweep plus its guard is a separate tracked change. Never run the sync expecting it to help, and never overwrite live profiles with tree copies to "fix" drift (that destroys live-only lessons the tree lacks — restore from backup immediately if it happens, then fold live content INTO the tree before any honest sync).
