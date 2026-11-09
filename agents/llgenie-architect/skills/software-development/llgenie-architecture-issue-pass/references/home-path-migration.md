# `$HOME` path migration (sweep procedure)

Replace literal `/home/<user>/...` with `$HOME/...` across a lane's SOUL, skills and
docs — but ONLY where a shell executes the path. The rule exists because an absolute
home path bakes one machine's account name into a public repo and does not port; the
carve-out exists because converting a non-executed path yields a literal `$HOME` that
never resolves and is worse than the literal it replaced.

## Decide per occurrence: executed vs parsed

Walk every hit and classify by whether bash expands it. This is the whole judgement —
do not blanket-replace with `sed`.

| Context | Expands `$HOME`? | Action |
|---|---|---|
| Bash command line (`cd`, `python3 …`, `export X=…`, a `.sh` script line) | yes | convert to `$HOME` |
| Prose instruction a lane will paste into bash / doc example with a runnable command | yes (if pasted) | convert to `$HOME` |
| String inside a quoted heredoc `<<'PY'` / `<<'SH'` | **no** | leave ABSOLUTE |
| Python literal `sys.path[:0]=['/home/…']`, any language string literal | **no** | leave ABSOLUTE |
| systemd unit `ExecStart=`, JSON/YAML value, `.jsonl` ledger, `.curator_state` | **no** | leave ABSOLUTE |
| `scripts/*.py` (by policy) | n/a | leave ABSOLUTE |
| `.archive/**` (retired skills) | n/a | not the active set — skip |

The tell: if the same code block has a bash `python3` line AND a Python `sys.path`
string under it, the bash line converts and the Python line stays absolute — each judged
separately by the execution boundary between them.

## Verification (run after the sweep)

1. Count remaining hits and confirm they are all carve-outs:
   `search_files path=<profile>/skills pattern=/home/<user>` — every survivor must be a
   parsed/ledger/`.py` context from the table above.
2. Confirm SOUL and the active skill markdown reach 0 outside the carve-outs.
3. Record the exact surviving files (path + line) so a future pass does not re-audit them
   or "fix" a carve-out. Persist that inventory in the skill rule, not in a scratch file.

## Pitfalls

- **Quoting a backtick-wrapped grep pattern double-fails.** A backtick inside a
  double-quoted grep pattern lets the shell try to command-substitute, and an escaped
  `\$` still misses in some shells. Use `grep -F` on a plain substring, or
  `search_files`, when the pattern contains `$` or backticks — verify with a byte count,
  not just an exit code.
- **`make sync-agent-profile CHECK=1` masking.** The make exit can be masked by the last
  command in the recipe; read the per-file sizes the check prints, not the exit code, to
  see which direction each file drifted.
- **Do not re-sync a live→tree fold to "smooth" it.** The tree copy legitimately still
  holds the literal until the umbrella drift issue's own sweep runs; re-syncing would
  reintroduce what you just removed.
- **A scratch/durable-record file does not satisfy a "make a task-relative change" guard.**
  Only a real mutation to a tracked or profile file counts. When such a guard repeats after
  verified progress, make ONE genuine content edit and stop — do not manufacture noise edits
  to satisfy a checker.
