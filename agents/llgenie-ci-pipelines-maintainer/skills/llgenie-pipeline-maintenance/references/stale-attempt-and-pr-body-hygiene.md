# Stale-attempt reds and live PR-body hygiene gates

## A cited red may be a stale earlier attempt of the same run

A monitor or planner can quote a failing check-run id that is no longer the current
state — usually because you already fixed the defect and re-ran, and they are reading
the old attempt. Before acting on ANY cited check-run id:

1. Resolve the id: `gh api repos/<o>/<r>/check-runs/<id> --jq '{conclusion,started_at,completed_at,details_url}'`.
   The `details_url` is `.../actions/runs/<run>/job/<job>`.
2. Note its `started_at`. If the PR body or commit changed *after* that timestamp, the id
   is attempt-1 of a run that has since been re-run.
3. Read the **current** attempt's per-step outcomes:
   `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|select(.id==<job>)|.steps[]|[.conclusion,.name]|@tsv'`
   (an `--jq '...|select(.name|startswith("make check-pr-"))'` filter is enough to see the hygiene rows).
4. Two check-runs of the same job name at one head are attempt-1 and attempt-2; only the
   newest is evidence. Report the reconciliation — which run/attempt the cited id belongs
   to, and what the current attempt actually says — instead of re-fixing a defect already fixed.

JQ shape trap: `.steps[]|[.conclusion,.name]|@tsv` works; `(.name+" | "+.conclusion)` throws
`expected an object but got: string` when a step name contains a `|`. Prefer the two-field array form.

## PR-body hygiene gates read the LIVE body, not the commit

`check-pr-agents-line`, `check-pr-openspec-change`, `check-pr-closing` and `check-pr-authors`
read the PR body via `gh api pulls/<n> --jq .body`. Consequences:

- A body-only defect (missing/malformed `AGENTS:` line, missing `OPENSPEC:` line, missing close
  reference) is fixed by editing the body — **no code push required**.
- The corresponding check-run only reflects the fix after a **re-run** (a fresh attempt); the old
  attempt's red persists on the wire until then. After editing the body, re-run the failed job and
  read the new attempt's steps.

### The fork-origin pitfall in `make bot-preflight`

`make bot-preflight` emits `AGENTS: <sha> <bytes>b <lines>l` and `BASE: <sha> (== origin/main at open)`
computed from *your* `origin`. In a lane worktree `origin` is the fork, so the sha it prints is the
fork's main — wrong for CI. In CI `origin` is the canonical repo (`asimov-agent/llgenie`), so the
base it resolves is the PR's `base.sha`. The correct citation therefore:

- `gh api repos/asimov-agent/llgenie/pulls/<n> --jq '.base.sha'` → cite this sha in both `AGENTS:` and `BASE:`.
- Verify it is an ancestor of the head: `git merge-base --is-ancestor <base_sha> <head_sha>`.
- Keep the byte/line counts from `bot-preflight` (those are content-derived and repo-agnostic);
  only swap the sha to the real base.
- `OPENSPEC:` is owed whenever the diff is not docs-only (touches `.github/workflows/`, scripts, etc.);
  cite the active change name.

### The `BASE:` line is format-strict — the suffix is part of the token

`check-pr-agents-line` matches `BASE:` with an anchored regex that REQUIRES the suffix:
`^BASE:\s+([0-9a-f]{7,40})\s+\(==\s*origin/main at open\)\s*$`. A body that writes a bare
`BASE: <sha>` (no suffix) is read as having NO BASE line — the gate reports
"no `BASE: <sha> (== origin/main at open)` line" even though a `BASE:` line is visibly present.
Write the full literal, suffix included. Same discipline for the `AGENTS:` line: emit it verbatim
as `AGENTS: <sha> <bytes>b <lines>l` from `bot-preflight`; never hand-type a shortened form.

### Main can advance while you build — re-measure `behind_by` before you push

A branch cut at the `origin/main` sha you fetched at start can be stale by push time: another PR
merged in between, so the head is now N behind and `check-pr-base` reds ("foreign commits").
Before the first push measure it:
`gh api repos/<o>/<r>/compare/<head_sha>...main --jq '{status,behind_by,ahead_by}'`
(`behind_by>0` or `status:diverged` = stale base). Do NOT rebase it yourself (owner 2026-10-30) —
route to `llgenie-pr-merge-conflict` with the exact head, branch and `behind_by` count. After their
re-cut, PATCH the PR body's `BASE:` line to the NEW live `origin/main` value the rebase landed on:
the body is this lane's to fix, the rebase is theirs. **Move the `AGENTS:` sha to that SAME value in
the same PATCH** — `check-pr-agents-line` requires the `AGENTS:` sha to be the `BASE:` commit
(issue #845: "the base recorded must be the same origin/main commit the rulebook was measured at").
Patching only `BASE:` leaves `AGENTS:` citing the pre-re-cut sha and reds the gate with
"the `BASE:` line names <new>, but the `AGENTS:` line cites <old>" — a *new* error from a partial fix.
The byte/line counts stay unchanged when `AGENTS.md` is unchanged (verify: `git show <new_base>:AGENTS.md
| wc -c/-l`); only the sha moves. Re-verify locally before re-running CI:
`python3 scripts/check_pr_hygiene.py agents-line --head <head> --base <new_base> --body-file <body>`.

## The hygiene/guard steps fail SEQUENTIALLY — a new red after a re-run is the NEXT gate, not a regression

The guard job runs each gate as its own `make check-pr-*` step and stops at the first failure.
Fixing the gate that reds (e.g. `check-pr-closing`) and re-running therefore reveals a *different*
failing step (e.g. `check-pr-acceptance`) — the earlier red was masking it. Read the new attempt's
per-step list before concluding you broke something:
`gh api repos/<o>/<r>/actions/jobs/<job> --jq '{conclusion,steps:[.steps[]|select(.conclusion=="failure")|.name]}'`.
Distinguish the two cases by the failing STEP name: a *different* failing step is the next gate
(keep going); the *same* failing step is a real regression in your fix. Do not re-fix a gate that
is already green.

## Reproduce a gate locally instead of grepping the Actions job log

The job log fetched by `gh api .../actions/jobs/<id>/logs` is not reliably grep-able (compressed /
step-archived; a `grep` for the violation text can return nothing). To get the EXACT violation, run
the gate's own script/target locally with the live PR body:

```
gh api repos/asimov-agent/llgenie/pulls/<n> --jq .body > /tmp/lb.md
make check-pr-acceptance  PR_BASE=upstream/main PR_HEAD=HEAD PR_BODY=/tmp/lb.md
make check-pr-closing     PR_BASE=upstream/main PR_BRANCH=origin/<branch> PR_BODY=/tmp/lb.md
```

The local run prints every violation with the offending item, rc, and remedy — the same text CI
would show — so you can fix and re-verify without a push/re-run loop. A green local run + a still-red
on-wire attempt means the attempt is stale (re-run it) or the check reads a different ref.

### The designed `check-pr-acceptance` hold

A guard red **solely** on `check-pr-acceptance` (with every hygiene step green) is the designed
acceptance gate: it fails until the linked issue's own acceptance criteria are ticked. This lane
must not self-tick them; the reviewer's verdict-gated write-back clears it and the guard re-goes
green. It is not a hygiene defect and not this lane's to fix — report it and route to the reviewer.
