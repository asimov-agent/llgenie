# Reword the standing force-push rule to name `--force-with-lease` for a rebase (issue #1960)

## What changed

The standing fleet rule "`--force-with-lease` protects against strangers, not your own older knowledge" was
reworded so it names the incantation a lane's own code actually pushes with, instead of the one that
rejects a true rebase. The old bullet said "Fetch immediately before any force, use `--force-if-includes`"
— contradicted by `scripts/rebase_bot.sh` (and `engine_bump_rebase.py` / `engine_bump_sync.py`), which
push a rebase with plain `--force-with-lease` after a fresh fetch (fetch at `scripts/rebase_bot.sh:100`,
push at line 263 on `main@d29ef77a`, measured 2026-11-09).

The corrected bullet, byte-for-byte across `agents/standing-rules.md`, all 13 `agents/*/SOUL.md` copies and
the pr-rebase splice source `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/references/standing-rules.md`:

> **`--force-with-lease` protects against strangers, not your own older knowledge.** After a fresh fetch of
> remote+head, push a REBASE with plain `--force-with-lease` — `scripts/rebase_bot.sh`'s own push line
> (`git push --force-with-lease "$REMOTE" "HEAD:$HEAD_BRANCH"`) is the example — because the tracking ref
> then holds the just-fetched expected value, and a rebased head does NOT contain the old remote tip, so
> `--force-if-includes` would rightly refuse it. Use `--force-if-includes` only where the remote tip is an
> ancestor of the new head (an amend/integrate push). Treat a branch another lane repaired as read-only.

`--force-if-includes` is restricted to a push whose new head contains the remote tip (an amend/integrate),
matching the architect's own reference (`agents/llgenie-architect/skills/software-development/llgenie-architecture-issue-pass/SKILL.md`),
which already recorded that a true-rebase force is rightly refused. Premise confirmed empirically
(2026-11-09, git 2.56.0 scratch lab): after a genuine rebase, `git push --force-if-includes` returns rc=1
("non-fast-forward" / "behind its remote counterpart"), plain `--force-with-lease` after a fresh fetch
returns rc=0 ("forced update").

## Decisions taken

- The taught rule and the shipped behaviour are now the same incantation (`--force-with-lease` after a
  fresh fetch), so a lane never needs to strip a guard to push a legal rebase.
- The example cited is `scripts/rebase_bot.sh`'s own push line; the issue's `:203` lineage is not cited
  because the line number shifts with main (measured `:263` at `d29ef77a`).

## Current status

Doc-only change on branch `agent/issue-1960-force-push-rule` (off `main@d29ef77a`). Canonical
`agents/standing-rules.md` + pr-rebase splice source carry the corrected bullet and the change→note trio is
in place. The 13 `agents/*/SOUL.md` verbatim copies are the same bullet; those files are
protected-instruction writes that land on the owner's live-consent prompt. Once consented, re-run the
master SOUL splice and the fleet-profile gates and open the ready-for-review PR closing #1960 — lanes open
per-profile SOUL PRs are unmerged at this write, so the mirrors must move in this PR for
`check_agent_profiles.py` and the splice idempotency test to be green.
