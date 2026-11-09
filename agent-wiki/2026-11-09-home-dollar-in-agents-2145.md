# agents + docs: `$HOME`, never `/home/<user>` (issue #2145)

Behavioral-surface change: the instruction text a credential-holding lane runs under must not bake
one host's account name into the versioned tree. This change sweeps the tree and adds a gate so the
literal cannot return.

## What was measured (at the filing sha, tree-only)

```
git grep -n '/home/asimov' origin/main -- 'agents/**/*.md'
40 occurrences across 17 files   ->  0 occurrences across 0 files
```

None of those `.md` occurrences were a genuine non-shell carve-out (no systemd unit, crontab, or
parsed YAML/JSON lives under `agents/**/*.md`); every one was a shell command, a path in prose, or a
path named in a rule-text line. Each became:

- a shell command (`cd`, `git -C`, `git worktree add`, `find`, `stat`) → `"$HOME/..."`;
- a prose/backtick path → `$HOME/...`;
- the `<user>` placeholder in rule text that names the convention → `/home/<user>`.

The `.py` / `.sh` files under `agents/**` were left untouched: per the issue's scope note a Python
literal needs a real path or `pathlib.Path.home()`, and `scripts/*.py` is a different lane's
surface. The gate deliberately scans `agents/**/*.md` only.

## The carve-out (stated, not silent)

A context that does **not** run through bash — a systemd unit (`ExecStart=`, `EnvironmentFile=`,
`WorkingDirectory=`), a crontab line outside a shell, a `YAML`/`JSON` value consumed by a program —
must **not** use `$HOME`, because nothing expands it there. Those keep an absolute path or the
native form (`%h` in systemd). A real systemd unit is a `.service`/`.timer` file, never a `*.md`
instruction, so this gate cannot red the carve-out by construction. Within an `.md`, a documented
placeholder (`<user>`, `user`) or a container-image user (`/home/agent`, `/home/root`) is allowed;
a concrete account is not.

## The gate

`scripts/check_agent_profiles.py` gains a `home-path-literal` finding (added to `KNOWN_KEYS` and
wired into `findings()`), so `make check-agent-profiles` reds on any reintroduction, naming the
file. `tests/test_home_paths_gate.py` drives the real gate with a temp tree and negative controls
(clean → green; one-line `/home/asimov` → red naming the file; carve-outs/placeholder/`scripts/*.py`
→ not red), and the existing `test_committed_tree_passes_the_gate` on the committed tree fails in CI
on a departure.

## Reference

- Issue #2145 (owner rule delivered to all 13 lanes 2026-11-08; tree sweep + gate is this change).
- Carve-out precedent: the planner rule text and this lane's `references/authoring-and-delivery.md`.
