# Trailing-newline trap (ci-lint / `scope` job)

A new markdown file written by `write_file` may land without a final newline. `make ci-lint`
(`python scripts/lint_linefeeds.py`) then reds the `scope` job on the branch.

## Why a local run looks clean and lies

At base the new files do not exist, so the linefeed scan never sees them; the gate runs against the
branch head that includes them. Never conclude "lint is clean" from a run against a tree that does
not contain the added files.

## Proof

The linter names each file; quote that `file` name, not the red badge. Then read the last BYTE in hex —
not with `od -c`, which is ambiguous (see the trap below).

```
tail -c1 <file> | od -An -t x1      # 0a = newline (good); 20 = space, 09 = tab (bad); any hex = the culprit
python3 -c "import sys;print(sys.stdin.buffer.read().endswith(b'\n'))" < <file>   # True = has newline
```

### The `od -c` trap: a trailing SPACE reads as a newline

`od -c` renders a real newline byte as the two characters `\` `n` AND terminates its own output line with
a newline. So `tail -c1 <file> | od -An -c` prints whitespace-then-`\n` for BOTH a trailing newline and a
trailing space/tab — a `\n` at the end of the od line does NOT prove the file ends in a newline. Measured
here: a change-note whose last byte was a space (`0x20`) round-tripped through `git show <sha>:<path>` and
`od -c` and looked fine, so the red was nearly dismissed as stale — while the linter, `python … endswith`
and `git diff` (`\ No newline at end of file`) all correctly flagged it. **When the linter and a readable
byte check disagree, the readable bytes are lying: trust `od -An -t x1` / python `endswith(b'\n')` / the
diff marker, never a `\n` glimpsed in `od -c` output.** Also note `git show <sha>:<path>` reads the
COMMITTED blob while the linter scans the WORKING TREE — a clean `git status` plus identical sizes is the
precondition for comparing them; a space-heavy blob can end `\n` in the commit and still be the same file
on disk, so measure the on-disk file the linter actually read.

## Fix, inside the same atomic commit

```
python scripts/lint_linefeeds.py --fix
# amend the existing commit (remote tip stays an ancestor), then git push --force-with-lease --force-if-includes
git show <new-head>:<path> | tail -c1 | od -An -c   # expect a newline
```

## Proving it: host linter or CI, never the worktree container

`scripts/lint_linefeeds.py` discovers files via `git ls-files`, so in a `docker run -v <worktree>:/repo`
run it sees 0 tracked files and prints `LINT OK` vacuously (and the hermetic `test_lint_linefeeds.py`
reds `got 0 files` — see `hermetic-run-and-census-quirks.md`). The authoritative run is the linter on the
HOST worktree (a real git checkout): `python3 scripts/lint_linefeeds.py` must print
`LINT OK — all tracked text files end with a newline`. A host `LINT OK` after a one-byte `printf '\n' >>
<file>` is the proof; confirm with `tail -c1 <file> | od -An -t x1` = `0a` (NOT `od -c`, which hides a
space as below) and `git diff --stat` = `1 insertion(+), 1 deletion(-)`
(the `\ No newline at end of file` marker gone).

## When the rebase lane already moved the branch, re-apply as a NEW commit

A lint fix is a single-byte delta, so it is easy to replay cleanly: if `git push` is rejected
`non-fast-forward` because `llgenie-pr-merge-conflict` has rebased the branch onto a fresh base, do NOT
force-push your pre-rebase commit over their head. Fetch their head, `git checkout <branch> && git reset
--hard origin/<branch>`, confirm the newline is still missing on THEIR head, re-append the one LF as a NEW
commit on top, and **fast-forward** push (`git push origin <branch>`, no force). The rebase lane's renumbered
history is preserved and your delta lands on the live base.

## Stale-head pins
The reviewer lane may pin a lint red at a sha you already superseded. That is not a new defect:
fix (or confirm the fix) at the current head and state which sha the red was measured at, so the
other lane stops reading a dead run.
