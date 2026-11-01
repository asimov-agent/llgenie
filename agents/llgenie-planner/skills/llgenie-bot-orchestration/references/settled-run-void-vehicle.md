# A lane blocked on a "settled" run, or circling a void vehicle, is idle — measure and force

**Trigger:** a lane's status reply names a run as in-flight ("pending settle") or a mergeable head
that #the API says is not there. Two recurring shapes from 2026-11-01:

## 1. The run settled LONG ago; the lane still waits for "the wake"

A lane claims run `X` is still `in_progress` with one cell pending, awaiting completion. Check the
API, not the prose:

```bash
gh run view <RUN> --json status,conclusion,headSha,updatedAt,createdAt \
  --jq '{status,conclusion,head:.headSha[0:8],updatedAt}'
gh api "repos/asimov-agent/llgenie/actions/runs/<RUN>/jobs" \
  --jq '[.jobs[]|{name:.name[0:30],status,conclusion}]'
```

Measured twice in one evening: `41338721917` (claimed "linux/unit sole remaining IN_PROGRESS") and
`41337589617` (claimed "need it to settle before push") were BOTH `completed/failure` with an
`updatedAt` 60–84 minutes before the read, and neither gated the branch's current head. A lane
awaiting "the completion wake" of an already-settled run is parked on a void gate — the block must
be removed by evidence.

## 2. The vehicle is void: head not on any remote ref, or PR already merged

- `git ls-remote origin | grep -c <head>` → 0 means the cited head exists only locally.
- `gh pr view <n> --json state,mergedAt,mergeCommit` → CLOSED/MERGED means no live head remains to
  rebase; the diff is on `main` (post-merge discipline #1446/#1402: do NOT revive the head).
- A local commit whose parent is an OLD base (`git log --oneline -2 <sha>`) while the remote branch
  (`git ls-remote origin refs/heads/<branch>`) is a DIFFERENT, richer sha = the lane is describing a
  stale local slice; the pushed vehicle already contains the change and more.

Engine case: remote `llgenie-wt/vllm-rust-fix` = `68e25cdb` (4-file/42-line vs `origin/main`),
while the lane's DM cited local `895d5761` (parent `dd47882a`, narrower diff, 404 on the ref API).
The block ("not pushed pending the run") was void on BOTH counts — the work was already pushed.

The missing artifact when the work is pushed but the issue is open: the **PR**, not another push.
Direct the lane to open the PR from the remote branch sha onto current `origin/main`, one vehicle,
`AGENTS:` line, run-id evidence — and never force-push the stale local slice over the remote.

## 3. The vehicle is a CLOSED duplicate — a DIFFERENT PR closed the issue

A lane asks you to "confirm the PR number" for its branch (blank readback after `gh pr create`).
Resolve it by branch, never by guess:

```bash
gh pr list --head <branch> --state all --json number,state,mergedAt,mergeCommit \
  --jq '.[]|{n:.number,st:.state,mergedAt,mc:(.mergeCommit.oid[0:8])}'
gh pr view <n> --json closingIssuesReferences,state --jq '{st:.state,closes:[.closingIssuesReferences[].number]}'
gh issue view <issue> --json state,closedAt
```

Shape seen 2026-11-01 (#1448): the lane's branch mapped to a PR **CLOSED** (never merged) while the
issue was CLOSED by an entirely different, already-MERGED PR (#1449, merge `fbb5f6bd`). The lane's
"done" was therefore true of the *content* and false of the *vehicle*. Do: give it the real number,
state plainly that the PR is closed as a duplicate, name the PR that actually landed (number + head +
merge sha + `closes #n`), and tell it **do not resurrect the closed duplicate** — the fold is already
on `main`. Measure the byte-identity md5 at the *landed* PR's merge commit, not the lane's head.
A lane whose md5 matches the shipped tree but whose PR is CLOSED has done the work right and picked
the wrong vehicle: verify the tree, correct the vehicle, no re-commit.

## 4. Verify the correction landed

Post the reconciliation board-durable (never DM-only; #the API is the evidence), then read the
comment back (comment id, issue number, each key claim as a substring true). Name the run's true
`status/conclusion/updatedAt`, the true head, and the run(s) that genuinely meet/accepted the
gate on `main`. No merge/arm (#1088).

## 5. A quoted "current main" is itself a claim — re-resolve it before you inherit it

Repeats every time a lane's report lingers: the lane names `main <sha>` as the current base when
that sha is the *merge commit of the vehicle it is talking about*, now several merges behind. One
evening produced `07342a11`, `91b1eb4d`, `506a9fb4` cited as "current main" while `origin/main` was
`2998925a`. Always re-run `git fetch origin main && git rev-parse --short origin/main` and quote the
fresh sha; if you are re-using the lane's sha in a board comment, call it the **audited / measured
point-in-time**, never "current main". The same applies to a report that a PR is OPEN/MERGEABLE: read
`gh pr view <n> --json state,mergedAt` — a pre-merge echo describing an in-flight head reads as a
phantom once the PR is MERGED, and the fold is already on `main`.

When the refutation is posted once with a **timestamp** (`updatedAt` of the run, `mergedAt` of the
PR), the evidence is stronger than any prose and later identical echoes need no reply — they are
pre-correction replays of a settled state, not new facts. Log the item, do not re-dispatch.
