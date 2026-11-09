# Force-push rule corrected to plain --force-with-lease after a fresh fetch

Issue #1960. Corrected the contradictory standing rule so the documented push behaviour matches what
the scripts actually run.

## What was wrong

`agents/standing-rules.md` line 17 said "Fetch immediately before any force, use `--force-if-includes`"
— an unconditional `--force-if-includes`, which REJECTS a force whose remote tip is not an ancestor of
the new head. A lane that rebases onto a moved base then forces a rebased head that does not contain the
current remote tip: `--force-if-includes` refuses it. The scripts never push that way — `scripts/rebase_bot.sh`
(lines 100/111 fetch, line 263 `git push --force-with-lease`) and `scripts/engine_bump_sync.py` (fetch:101,
push:120-124) all push plain `--force-with-lease`.

## The corrected rule

- For a rebase, **fetch immediately before any force** and push **plain `--force-with-lease`** — the
  scripts' own shape, `scripts/rebase_bot.sh` line 263 after its fetch.
- Use `--force-if-includes` **only when the remote tip is an ancestor of your new head**, since it
  REJECTS a force whose remote tip is not.
- The touch-line is kept: a branch another lane repaired is read-only.

## Files

- `agents/standing-rules.md` line 17 (the rule) and its line-29 rebase entry (dropped the `/--force-if-includes`
  alternative).
- `agents/llgenie-architect/skills/software-development/llgenie-architecture-issue-pass/SKILL.md` after
  line 358 — the reference already carried correct (a)/(b) behaviour; now cites `scripts/rebase_bot.sh`'s
  plain `--force-with-lease` push (line 263) as the example.

No scripts, tests, or workflows changed.
