Write `$HOME`, never `/home/<user>`, in anything this profile authors (standing owner rule).

Every lane shells through bash, so `$HOME` resolves in any command, path or prose example; the absolute
form encodes one machine's account name in a public repository and is non-portable. Use it in SOUL.md,
skills, references and docs examples.

## The carve-outs — do NOT "fix" these
- A context that is _parsed, not executed_ must keep the literal: nothing expands `$HOME` there. That
  means systemd units (`ExecStart=`, `EnvironmentFile=`, `WorkingDirectory=` — use `%h` instead),
  crontab lines outside a shell, and YAML/JSON values consumed by a program.
- A **Python string literal** (including inside a heredoc a markdown skill passes to `python3 -`) must
  keep a resolved absolute path or build from `pathlib.Path.home()`. Rewriting it to `$HOME` yields a
  literal `$HOME` that never expands — worse than the literal. A `sys.path[:0]=['/home/<u>/…']` line in
  a skill's python heredoc is exactly this case: the interpreter path on the same line is shell (use
  `$HOME`), the string argument is Python (keep absolute).
- `scripts/*.py` are left alone entirely.

## Verification (host-proven, actual run)
Both halves execute on this host:
- `test -x "$HOME/.hermes/hermes-agent/venv/bin/python3"` → executable; the absolute form
  `/home/<u>/.hermes/…` also exists, so the shell line is safely `$HOME`.
- The python string cannot be rewritten: `os.path.exists("$HOME/.hermes/hermes-agent")` → False — a
  literal `$HOME` in a Python string is parsed as the 5 characters, not expanded, and is not a
  directory. That is why the `sys.path[:0]=[…'/home/<u>/…']` lines must stay absolute.

## Verify before declaring done
`grep -rn '/home/<u>' <profile>/SOUL.md <profile>/skills/` — every remaining hit must be a Python
string, a `.jsonl`/`.curator*` program-state file, a `scripts/*.py`, or `.archive/` retired content.
Every shell/prose hit must read `$HOME`. Do not run `make sync-agent-profile` to propagate — the tree
copy may still hold the literal, and a sync would re-introduce it (tree sweep is its own issue).
