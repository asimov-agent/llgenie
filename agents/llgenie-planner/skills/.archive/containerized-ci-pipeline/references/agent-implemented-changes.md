# Agent-implemented change etiquette (this class of repo)

Rules for an implementing agent in a bot-driven repo whose rulebook (AGENTS.md) is
machine-enforced and largely protected from agent writes.

## AGENTS.md is a protected file — the "owed row" workflow

`AGENTS.md` is a PROTECTED agent-instruction file: the `patch` tool refuses to write
it (the approval prompt times out), and retrying or rerouting through
t`terminal`/`execute_code` is also refused. Yet the repo's own rules (AGENTS.md §8
regression-guard rows, rulebook wording) frequently require editing it inside a
change. The agent CANNOT do that step. The correct workflow, not a workaround:

1. Do NOT loop on the edit or try alternate write paths — they are refused too.
2. Tick the OpenSpec task as "the AGENTS.md row is owed", and file a `tech-debt`
   issue carrying the exact owed text: a §8 guard row naming the test(s) + what
   they catch + the issue ref, with a `tech-debt-signature` HTML-comment marker
   (the dedup key `make file-findings` searches for) and an Origin note saying a
   protected file forced the separate filing.
3. Say in the PR body that the `AGENTS.md` row is owed by that issue.

A protected rulebook is the one legitimate case where a §8 row lands in a later
human change rather than the same one — matching the repo's own precedent of
filing an owed rulebook row as a `tech-debt` issue.

## Scratch output must live outside the checkout

A bot loop's between-round scratch file (e.g. the fix loop's notes, folded into the
report by the next round) must be `mktemp`'d under `${TMPDIR:-/tmp}` and removed on
exit (`trap ... EXIT`), or covered by a `.gitignore` CLASS — never placed
beside an already-ignored file. A `.gitignore` that names `qa-report.txt` and `comment.md`
exactly does NOT ignore `qa-report.txt.notes`. The bot's `git add -A` commit step
stages it: an EMPTY one lands a 0-byte stray file in a data PR (blob `e69de29`); a
NON-empty one (a round killed by the fix timeout, a no-change round) publishes the
loop's own diagnostics into the very repository it is meant to repair.

Two guards, both proven RED against the pre-change tree:
- Drive the REAL loop with the production report path (relative, default name) and
a timed-out round; assert no `*.notes` sibling appears beside the report WHILE the
timeout reason still reaches the report.
- Run the REAL commit step in a temp clone carrying the repo's `.gitignore`, plant
`qa-report.txt.notes`, and fail the test if it reaches the pushed commit.

Preserve the information channel when you move the file: a timed-out / no-progress
round must still reach `qa-report.txt` (the PR comment reads that), only the scratch
temporary moves out of the tree.
