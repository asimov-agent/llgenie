# Bot-PR body gate: `AGENTS:`, `BASE:` and `SYNC:` lines, same origin/main sha

`scripts/check_pr_hygiene.py` gates the PR body on up to three lines. `AGENTS:`/`BASE:` are always
required; `SYNC:` is required ADDITIONALLY whenever the diff touches any `agents/<profile>/` path.

- `^AGENTS:\s+([0-9a-f]{7,40})\s+(\d+)b\s+(\d+)l\s*$`  → `AGENTS: <sha> <bytes>b <lines>l`.
  The cited sha must be an ancestor of BOTH head and base (`git merge-base --is-ancestor`, never
  equality — a rebase moves the merge base while the rulebook stays reachable from both sides).
- `^BASE:\s+([0-9a-f]{7,40})\s+\(==\s*origin/main at open\)\s*$`  → `BASE: <sha> (== origin/main at open)`.
  Its sha must EQUAL the `AGENTS:` sha, or the base-line finding fires.

## The `SYNC:` line — required when the diff touches `agents/<profile>/` (issue #1724)

The `check-pr-sync-line` gate reds a PR that edits any file under `agents/<profile>/` unless the body
carries one line PER touched profile:

    SYNC: <profile> make sync-agent-profile PROFILE=<profile>

Exact regex (`SYNC_LINE` in `scripts/check_pr_hygiene.py`):
`^SYNC:\s+([A-Za-z0-9_-]+)\s+make sync-agent-profile PROFILE=\1\s*$`. The `\1` backreference forces
the profile named after `SYNC:` and after `PROFILE=` to be identical — a mismatched pair does not
match. The finding is anchored at the merge-base, not the literal range start, so only genuine
same-PR `agents/` edits demand the line (a rebase onto a base that already carried the edit does not).

`AGENTS:` and `BASE:` alone do NOT satisfy this gate — it is a separate check that reads the body's
`SYNC:` lines. A PR touching `agents/llgenie-pr-reviever/` needs:

    SYNC: llgenie-pr-reviever make sync-agent-profile PROFILE=llgenie-pr-reviever

One line per touched profile, one blank-line-separated block is fine. Add it to the body in the same
pass as `AGENTS:`/`BASE:` — a body that carries all three greens at once instead of re-redding on the
third gate.

## Why a one-line fix re-reds

Adding `AGENTS:` alone still fails on a missing or mismatched `BASE:` line — a fix that touches only
one of the two is incomplete. Existing body prose like `· base: <sha> (current origin/main)` is NOT
the required `BASE:` line and does not satisfy the regex.

## Generate both from the canonical path

`make bot-preflight` (`scripts/bot_preflight.py`) writes both lines into `preflight.txt`. The
`bytes`/`lines` are the size of `AGENTS.md` at the `origin/main` sha: `len(text.encode())` and
`text.count('\n')` (note `count('\n')`, so a file with no trailing newline reports one fewer line).

To compute by hand at a given main sha:

    git show <main-sha>:AGENTS.md > /tmp/a.md
    python3 -c "b=open('/tmp/a.md','rb').read(); t=b.decode(); print(len(b),'b',t.count(chr(10)),'l')"

## Verify the gate's real expectation from source, never the stated fix

A dispatch or instruction naming the remedy (`add the AGENTS: line`) can be a strict subset of what
the gate checks. Read `agents_line_findings` in `scripts/check_pr_hygiene.py` and the exact regexes
before naming a fix, or the PR re-reds on the half you left out. The gate's source is the authority,
not a paraphrase of it.

## A body edit does not start a run

The guard reads the LIVE PR body each run (same fetch as `check-pr-closing`), but editing the body
alone re-triggers nothing. Push a no-op commit or re-run the workflow so the guard re-evaluates the
fixed body — otherwise the red you are trying to clear persists at the old run. Re-run the specific
failing run ids (`gh api repos/<owner>/<repo>/actions/runs/<id>/rerun -X POST`), then poll the fresh
jobs to a real conclusion; a `rerun` that returns an empty body still re-queues the jobs (new job ids
on the same run id), which is the signal it landed.
