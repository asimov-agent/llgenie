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
BAD   printf '%s\n' "text with `some-command` inside" | gh issue comment N --body-file -
GOOD  write the body to a file, then:  gh issue comment N --body-file /tmp/body.md
GOOD  gh issue comment N --body 'single-quoted, backticks are literal'
```

**`printf "…"` is the same defect wearing a hat.** The format argument is still a double-quoted
string, so its backticks are command-substituted before `printf` ever sees them. Shell prints
`command not found` for each code span and the comment posts with the spans silently removed —
it exits 0, the URL comes back, and the body is quietly mangled. If a body carries inline code,
`write_file` then `--body-file <path>`, or a single-quoted heredoc; never a double-quoted argument
to any command (`printf`, `echo`, `gh … --body`).

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

## A refused write leaves the OLD body on disk — posting it publishes stale text

The guard blocks the write; it does not clear the file. When a later command in the same turn does
`gh issue comment N --body-file <that same path>`, `gh` reads the **previous** session's body and
posts it verbatim under a fresh comment id. The call exits 0, the read-back shows a new id, and the
content contradicts the current board — the worst combination: it looks verified, and it is wrong.

- After a `stale_write_blocked` refusal, treat that path as poisoned for the rest of the turn. Never
  `--body-file` it until you have re-written it under a unique name or switched to the stdin heredoc
  above; the heredoc form removes the failure class outright and is the default for board comments.
- **Verify content, not just the id.** A read-back that returns `{"id": …, "head": <first 60 chars>}`
  is the minimum bar — read that first line and confirm it is the body you just wrote. Citing an id
  you never eyeballed is how a stale post survives into the next pass as "already covered".
- **`.[-1]` is not "my newest comment".** The comments API returns in the order it returns, and a
  just-created comment can sort *below* an older one (list ordering, import timing). A read-back that
  grabs `gh api …/issues/<n>/comments --jq '.[-1]'` can hand you a week-old body and you will read it
  as "my post failed". Never conclude failure — or re-post — from `[-1]`. Query the specific thing:
  `gh pr comment <n> --body-file …` prints the comment URL; take that id and GET it
  (`gh api repos/<o>/<r>/issues/comments/<id>`), or filter the list for it. Verify by **id +
  created_at**, and only then report the mutation as landed.
- When you build a body file, echo its first line back before posting (`head -c 200 <path>` alongside
  the POST, or the heredoc itself), so a refused write is caught before it reaches the board.

## Recovery: repairing a comment that already posted mangled

When the trap fires anyway — the URL comes back, the function exits 0, but the body reads
`is / (updated 15:47:45Z)` where `completed/cancelled` should be — do **not** post a fresh
corrective comment on top (that leaves two bodies, the broken one still authoritative to a
reader scrolling up). Repair in place: fetch the comment, rebuild the full body correctly, and
`PATCH` it. Build the JSON payload in **Python** (`json.dumps`) so the backticks never re-enter
a shell string:

```bash
python3 - <<'PY'
import json,urllib.request,os
tok=os.popen('gh auth token').read().strip()
body=open('/tmp/body.md').read()          # correct body written by write_file
req=urllib.request.Request(
  'https://api.github.com/repos/<o>/<r>/issues/comments/<id>',
  data=json.dumps({'body':body}).encode(), method='PATCH',
  headers={'Authorization':f'Bearer {tok}','Accept':'application/vnd.github+json'})
print(json.load(urllib.request.urlopen(req))['updated_at'])
PY
```

Then verify the read-back (`completed/cancelled present: True`, corrected first line) before
moving on — the PATCH succeeding is not the fact; the corrected body on re-GET is. `gh api
... -X PATCH -f body=...` also works but re-exposes the body to shell quoting; the Python
payload does not. (Shorter forms: `gh api repos/<o>/<r>/issues/comments/<id> -X PATCH -F body=@/tmp/body.md`.)

The same PATCH-in-place rule covers a **stale-content** post (old body published under a new id):
repair that comment rather than stacking a second one. Only when the stale comment is a near-duplicate
of an existing older one is it legitimate to post the correct body as a new comment — and then its
first line must state that the prior comment is superseded and not to be trusted. Either way, a reader
scrolling the thread must end up with exactly one authoritative body.

## Never chain setup steps you must verify

`git worktree add … && cd … && <gate>` fails as one opaque exit code: if the `add` refuses (path
already registered, branch checked out elsewhere), every later command in the chain never runs, and a
`cd` that silently kept the old cwd makes the *next* compound command appear to succeed against the
wrong tree. Symptom: the gate reports "No rule to make target" or measures a stale head, and the tree
is blamed instead of the chain.

- Run the worktree creation as its own call and trust the returned `cwd` over any `cd` you prefixed.
- Run the gate as its own call in that cwd — one call per failure mode keeps the failure legible.
- After any `git`-based measurement, confirm the head you actually measured
  (`git -C <tree> rev-parse HEAD`) is the sha you intended before quoting a result.

## Checklist before any comment or dispatch containing code

1. does the body contain backticks, `$(` or `$VAR`?  -> use `--body-file`;
2. if a command slipped through, check what it did **before** writing anything else;
3. report the incident where it happened, not only to the user — a reader of the issue must see it.
