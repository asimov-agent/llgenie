# Never put a command inside a quoted shell argument

**Incident:** a planner comment body contained the prune target name inside backticks, passed as
`gh issue comment … --body "… `make worktree-prune` …"`. Backticks in a **double-quoted** shell
string are command substitution, so the command **executed**. It removed 7 worktrees and deleted 2
branch refs. The content happened to be recoverable (both PRs had merged); that is luck, not judgement.

## Rule

**Any body containing a command goes through a file or single quotes — never an inline
double-quoted string.**

```
BAD   gh issue comment N --body "text with `some-command` inside"
GOOD  write the body to a file, then:  gh issue comment N --body-file /tmp/body.md
GOOD  gh issue comment N --body 'single-quoted, backticks are literal'
```

## Why this outranks convenience

- `--body-file` costs one `write_file` call and removes the class entirely.
- A destructive command does not ask for confirmation when it arrives as substitution rather than
  as the command you typed — nothing in the tool output says "you just ran it".
- The failure is silent until something is missing.

## Second rule, learned the same night

**A destructive action is a defect even when its target was recoverable.** "Nothing was lost"
answers *what happened*, never *whether it was allowed*. Pruning worktrees is owner-only to every
bot; a bot that exceeds it must say so immediately, in the place the action happened, and state the
damage assessment **and** that the assessment is not a justification.

## When the file tool refuses your scratch body (stale-write guard)

A persistent planner reuses scratch filenames pass after pass (`c1128st.md`, `c1139b.md` …). A later
session that did not itself create or read that path gets:

```
Refusing to overwrite <path>: exists but this task has not seen its full current content
```

That is the stale-write guard, not an error in your body. Two fixes, both cheaper than reading the
old file back:

- **Pipe the body straight to `gh` via stdin** — no scratch file, so nothing to guard:

```bash
gh issue comment N --repo <o>/<r> --body-file /dev/stdin <<'EOF' 2>&1 | tail -1
... body, backticks and $(cmd) all literal ...
EOF
```

  The single-quoted heredoc delimiter means no expansion — the same safety as a real `--body-file`,
  so this is *also* the safe form for a body containing a command. `gh issue comment … --body -`
  does NOT work (stores a literal `-`); stdin is only read by `--body-file -` / `--body-file /dev/stdin`.
  `2>&1 | tail -1` prints the comment URL, which is the verification that it landed.
- **Name scratch files uniquely per pass** (`body-<issue>-<shortha>.md`) instead of a reused
  `c<N>.md`. A fresh name never trips the guard; a reused one trips it every time the previous
  session's file is still on disk.

## Checklist before any comment or dispatch containing code

1. does the body contain backticks, `$(` or `$VAR`?  -> use `--body-file`;
2. if a command slipped through, check what it did **before** writing anything else;
3. report the incident where it happened, not only to the user — a reader of the issue must see it.
