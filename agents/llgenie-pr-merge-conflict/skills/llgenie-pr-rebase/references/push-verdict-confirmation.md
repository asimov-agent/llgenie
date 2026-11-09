# Confirming a rebase push: wire, gates, verdict

Rules for the stretch between "I pushed" and "I reported done". Each one exists because the easy
shortcut produces a confident sentence about something that was never measured.

## 1. A push line is not proof the PR head moved

`+ <old>...<new> HEAD -> branch (forced update)` proves the remote ref accepted your objects. It does
not prove the PR's head is your commit: a cross-repo (fork-hosted) PR reads `headRefOid` from the
fork, and the org remote can hold a same-named branch. Read it back, always:

```bash
git ls-remote <fork-url-or-upstream-url> refs/heads/<branch>   # the wire
export GH_REPO=<upstream-owner>/<repo>
gh pr view <n> --json state,headRefOid,baseRefOid,mergeable,mergeStateStatus
```

Report the sha you read back, not the sha you wrote. And check `baseRefOid ==` the main sha you cut
from in the same breath — a rebase that moved the head but left a stale base is not a rebase.

## 2. Fork-hosted heads: pin the lease to the fork's sha

A PR whose head lives on a fork is pushed to the fork URL, and the lease must name the sha **the fork**
holds (from `git ls-remote <fork-url>` moments earlier) — a lease pinned to the org remote's value, or
to a sha quoted in a message, either refuses or, worse, protects against the wrong actor:

```bash
git push --force-with-lease=refs/heads/<branch>:<fork-sha-just-read> \
  --force-if-includes <fork-url> HEAD:refs/heads/<branch>
```

A rejected lease means another actor moved the branch: re-fetch, measure whether it is already
resolved, report, stop. Never escalate to a bare `--force`.

## 3. Generated indexes: regenerate, never grep rows

For an index file a `make` target writes (`CHANGES.md` and friends), counting rows with `git grep`
proves nothing — the auto-merge and the generator format the same row differently, and a row you grep
for may legitimately not exist verbatim. The union check is the generator's own opinion:

```bash
make <index-target>          # e.g. changes-index; rc must be 0
git status --porcelain       # must be EMPTY -> the merged file equals a fresh generation
```

An empty porcelain after regeneration is the union proof; a non-empty one names exactly the side that
was dropped. Do not hand-edit the file to satisfy a grep.

## 4. Gate the touched tests, not the whole matrix

The evidence for a rebase push is the targeted container run for the files the PR actually touches,
plus `make check-docs` (and `make bot-preflight` when the repo has it):

```bash
docker run --rm -u root -v "$PWD":/repo:rw -w /repo <test-image> \
  python -m pytest <touched test files> -q
```

Run the suite(s) covering the changed subsystem, not the full suite on the host interpreter — a host
`pytest` on a tree whose unit suite is containerised measures a different environment and its reds are
unattributable. Disclose a pre-existing red on clean `main` as pre-existing instead of attributing it
to the branch or silently dropping it.

## 5. A fresh head has no check-runs yet

Immediately after a force-push, `actions/runs?head_sha=<new>` can return **empty** for minutes. Empty is
"not queued yet", never "no checks required". Do not conclude, do not report a verdict, and do not read
an empty rollup as green:

```bash
gh api "repos/$GH_REPO/actions/runs?head_sha=<sha>" --jq '.workflow_runs[0].id // empty'
```

Poll it from a **background** watcher (a tracked process with `notify`), and post the finish bookend
only when the guard job for that head has a real `conclusion`. A completion comment that arrives before
the run it describes is the defect this rule prevents.

## 6. Verdicts come from check-run conclusions, not a status column

Read `success` / `failure` / `cancelled` from `check-runs` (or job) `conclusion`. `cancelled` means the
run was superseded — *not yet*, not red. A conflicting PR reports an empty rollup because GitHub builds
no merge ref for it; that emptiness is the conflict's symptom, not a workflow fault.

## 7. Another lane's quoted head may be your own pre-rebase tip

When a lane dispatches "head moved again, please rebase", the sha they quote is often stale — sometimes
literally the tip you already replaced. Measure before touching anything: `gh pr view --json headRefOid`
plus `git ls-remote` for the real wire. If the wire already contains the change they describe, the
correct answer is a **no-action** reply naming the measured wire sha and base sha, plus the check-run
conclusions — rebasing again would destroy a finished, green head and burn a matrix.

## 8. Oversized inline shell payloads get rejected

Long one-liners that mix loops, `$()` expansions and quoting inside a single `command` string can be
refused by the command parser before anything runs (the payload is saved to a blocked-scripts file).
Write the loop into a script under the scratch dir with the file tool and execute `bash <script>` — the
same work, parsed once, and re-runnable while you poll.
