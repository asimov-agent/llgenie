# Lane verification mechanics

How to prove lane state on the wire, and the shell traps around worktrees.

## 1. A rebase exists only when the head moved

`updatedAt` on a PR advances when *anyone comments*. It is not evidence of a push.

```bash
gh pr view <n> --repo asimov-agent/llgenie \
  --json headRefOid,headRefName,mergeStateStatus,state,updatedAt \
  --jq '.headRefOid[0:10]+" "+.headRefName+" ms="+.mergeStateStatus+" upd="+.updatedAt'

# did anything ever build at the new sha?
gh run list --repo asimov-agent/llgenie --limit 25 \
  --json databaseId,name,status,conclusion,headSha,createdAt,event \
| python3 -c "import sys,json;[print(r['databaseId'],r['name'],r['status'],r['conclusion'],r['createdAt'],r['headSha'][:10]) for r in json.load(sys.stdin) if (r['headSha'] or '')[:8]=='<sha8>']"
```

Verdict rules:

- `headRefOid` == your verified release sha AND a run exists at it  -> pushed, verify the run.
- `headRefOid` unchanged (an older sha)                           -> **staged, not pushed**; say so.
- `updatedAt` newer than the head's commit time, head unchanged  -> that was a comment (often your own).

Never let a lane's "re-pushed" claim stand on `updatedAt`. Quote `headRefOid` and the run id.

## 2. Containerised unit gate vs a scratch venv

The repo's `tests/` conftest boots the live engine (it prints `[engine-runner] READY …`, starts a
serve process and binds a port). Consequently, in a scratch venv:

- bare `pytest tests/...` hangs until timeout, or exits 2 with a 0-byte log even under `2>&1`;
- `pytest --co` also hangs, because collection imports the same conftest.

The real gate runs inside the pinned test image (the repo's own `make`/`TEST_RUN` path). If that image
is unavailable, the runnable proxy at the new head is:

```bash
git diff --name-only <base> <head> | grep '\.py$' | while read -r f; do
  [ -f "$f" ] && python -m py_compile "$f" || echo "MISSING $f"
done
```

Report it as exactly that — "every changed module compiles at <head>; the container TU gate was not
exercised" — and never as "unit green". A compile check proves syntax, not behaviour.

## 3. Worktrees and the persistent shell CWD

`git worktree remove <path> --force` while the persistent shell is `cd`-ed into that path leaves the
shell's CWD dangling. Every later command then fails early with
`cd: <deleted path>: No such file or directory` (exit 126) — including commands whose first line is a
fresh `cd`, because the shell's starting directory is already gone.

Fix: after any worktree removal, pass an absolute `workdir` to the next terminal call instead of
prefixing `cd`. Sanity-check residue with:

```bash
git -C <repo> worktree list | grep -c <path>   # expect 0
```

Removing a worktree you created is fine; pruning *other* lanes' worktrees is owner-gated — measure with
`git worktree list --porcelain` and report, never delete.

## 4. Editing a GitHub body: write to a file, never command-substitute a heredoc

`BODY=$(python3 - <<'PY' ... PY)` breaks the shell — the heredoc inside command substitution ends the
substitution early and you get `unexpected EOF while looking for matching ')'`, then a half-applied edit.
Do the edit in three steps instead:

```bash
gh api repos/<owner>/<repo>/issues/<n> --jq '.body' > /tmp/body.md          # 1. fetch
python3 - <<'PY'                                                            # 2. edit the file
p='/tmp/body.md'; b=open(p).read()
old='- [ ] the exact existing line'; new=old+'\n- [ ] the new criterion'
assert old in b; open(p,'w').write(b.replace(old,new,1))
PY
gh issue edit <n> --repo <owner>/<repo> --body-file /tmp/body.md            # 3. write back
```

Then **verify the write landed** by re-reading, not by the exit code:

```bash
gh api repos/<owner>/<repo>/issues/<n> --jq '.body' > /tmp/check.md
printf 'ACs=%s  new-line=%s\n' "$(grep -cE '^- \[ \]' /tmp/check.md)" "$(grep -c '<distinct new phrase>' /tmp/check.md)"
```

Same rule for verifying a cron job's prompt text: pull it via `json.load` and test membership with a
**plain Python `in`**, not a shell `grep -q` against a string containing regex metacharacters (`/<lane>/`
falsely reads absent under grep escaping and sends you fixing a non-bug). One POST-bearing call per turn:
fetch → edit file → `--body-file`/`hermes cron edit` → re-read.
