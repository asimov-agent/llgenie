# Triaging a red run, landing the fix, proving it

Use when the user shows a run/job URL ("why is this failing?") or a merge-commit sha on `main` is red.

## 1. Read the failing job, not the run

```bash
gh run view <run> --repo asimov-agent/llgenie --json name,conclusion,jobs \
  --jq '{concl:.conclusion, jobs:[.jobs[]|{name:.name,concl:.conclusion}]}'
gh run view --repo asimov-agent/llgenie --job <job-id> --log 2>&1 | tail -60
```

One red job out of ~26 is the normal shape — the run URL hides which one. Locate the failing job first,
then read only its log. Map the log's last `make` line to the target (`make ci-<job>`), not to the workflow
step name: the step name is a sentence, the target is the gate.

When the log is a pytest failure, the useful part is the last 40 lines (the `FAILED` summary plus the
assertion's own message), not the head.

## 2. Decide flake vs regression before touching code

```bash
gh run list --repo asimov-agent/llgenie --workflow CI --branch main --limit 8 \
  --json databaseId,conclusion,headSha,createdAt --jq '.[]|"\(.databaseId) \(.conclusion) \(.headSha[0:7])"'
```

- Seven green runs then one red, and the pushed diff does not touch the failing path → transient class
  (network, runner, registry), not a regression. Say so plainly; do not invent a code cause.
- Check the diff: `git show --stat <sha>` — a red `top-tier`/`test-published` job on a commit that touched
  only `auto_merge.py` is not that commit's doing.
- The run-failure reactor files its own issue per red run (`ci: CI / <job> failed`). Search before filing:
  `gh issue list --search "<job>" --state open`. Comment the root cause onto the reactor's issue and file
  the code defect as its own issue, linked both ways.

## 3. Look for the fix already existing somewhere

A fix committed to a branch AFTER that branch's PR merged reaches no PR at all — it sits there, green
locally, invisible to review. Before writing the fix yourself:

```bash
git log --oneline -S"<the symbol or flag>" -- <path>        # does a commit already do this?
git merge-base --is-ancestor <sha> origin/main && echo IN MAIN || echo NOT IN MAIN
gh pr list --head <branch> --state all --json number,state,closedAt
```

A `MERGED` PR for that head branch means a newer commit on it was never proposed — cherry-pick it onto a
fresh branch off `main` instead of re-deriving it, and add the missing OpenSpec change / wiki record.

## 4. Remotes: `origin` is UPSTREAM here

```bash
git remote -v      # origin = asimov-agent/llgenie (upstream), fork = andyholst/llgenie
```

This checkout inverts the usual convention. `git push -u origin <branch>` publishes to the upstream repo,
not the fork. Push the PR head with an explicit remote (`git push -u fork <branch>`) and create the PR with
`--head andyholst:<branch> --repo asimov-agent/llgenie`.

Side effect worth using: a branch pushed to the upstream repo CAN be dispatched, which a fork branch cannot.

## 5. Live-verify a `workflow_dispatch`-only workflow

A credential/wiring fix in a dispatchable workflow cannot be dispatched from a fork head, so the weak answer
is "awaiting post-merge verification". If the branch exists on the upstream repo:

```bash
gh workflow run <workflow>.yml --repo asimov-agent/llgenie --ref feat/<branch>
# then read the step that matters, not the conclusion alone:
gh run view <run> --repo asimov-agent/llgenie --log | grep -E "push-check|may push|no-op|already"
```

Keep both remotes' refs identical (`--force-with-lease` on your own branch) so the dispatched sha and the PR
head do not diverge, and quote the actual line the step printed in the PR/issue — that is the evidence, the
"success" badge is not.

## 6. OpenSpec: the container writes as root

`make openspec-new NAME=<name>` creates the change dir as root, so the following `write_file` fails with
`Permission denied`. Fix ownership before writing prose:

```bash
sudo chown -R $(id -u):$(id -g) openspec/changes/<name>
```

`make openspec-validate NAME=<name>` rejects a requirement with no `#### Scenario:` block — every ADDED
requirement needs at least one scenario, each with `- **Test:**` naming the test.

## 7. Falsify the test before claiming it locks the bug

```bash
# 1. put the defect back by editing the file (it is usually already COMMITTED), 2. run, 3. restore
$EDITOR <source-file>          # e.g. re-inline the old contiguous string, or drop the fix
make -s <the gate that runs the test>   # or the single test in the test image, see below
git checkout -- <source-file>  # restore the committed version
git status --short             # must show ONLY your intended edits afterwards
```

Expect the CI symptom (the same exception the red job showed). Restore and re-run green. Report both runs;
"the test passes" alone does not prove it locks the behaviour.

**Never `git stash push <file>` for this.** Two reasons, both measured:

- The file is usually already committed, so the push has nothing to stash and creates no entry (or none
  for that path) — the "reverted" run then tests the FIXED source and passes, telling you the guard is
  broken when it is not.
- The stash list is shared by every worktree of the repo, so the following `git stash pop` applies whatever
  entry happens to be on top — another agent's in-progress work — and drops you into `UU` conflicts on files
  you never touched, with `Recorded preimage for …` in the output as the tell.

If that already happened: `git reset -q HEAD -- <conflicted files>`, `git checkout -- <those files>`, restore
any tracked file you deleted while cleaning up, and leave `git stash list` intact — the entry belongs to
someone else's branch, not to you.

## 8. Hub transport seams: a read timeout is not a `URLError`

A retry loop that catches `urllib.error.HTTPError`/`URLError` silently leaks read-phase timeouts: after the
connection is established, `http.client`/`ssl` raise the builtin `TimeoutError` (`socket.timeout` since
3.10), and `issubclass(TimeoutError, urllib.error.URLError)` is `False`. One stalled read then escapes a
bounded retry budget as a traceback, and a live-Hub acceptance test reports "must exit 0".

- Every retry seam must name `(urllib.error.URLError, TimeoutError)` — check the sibling seams agree
  (`hf_auth.hub_open` vs `llgenie_serve._hf_get` had drifted).
- Lock it with a **real** server that accepts the connection and never answers (`ThreadingHTTPServer` whose
  handler sleeps past the client timeout) — no monkeypatched transport. Assert: the stall is retried and the
  retry's payload returned; an exhausted budget raises the seam's own `SystemExit` naming the attempt count;
  the raw `TimeoutError` never reaches the caller.

## 9. A red unit job is often a test that pins the SPELLING

When both unit jobs fail on one assertion and the branch's behaviour is fine, read the assertion before the
code: admin/contract tests here split the `Makefile`/workflow text and assert a substring. Pinning a
*contiguous* command (`"scripts/a.sh && scripts/b.sh" in recipe`) reds the moment either command gains an
argument or an env assignment — e.g. passing `FIX_REPORT_FILE="$(REPORT_FILE)"` between them — while the
order and the behaviour are unchanged.

- Repair the assertion to state the INVARIANT, not the spelling: both commands present, the first's index
  before the second's, and both inside the same `bash -lc '…'` segment so they cannot drift into separate
  invocations. It still fails if the preflight is dropped or moved after the loop.
- **Do not revert the argument to satisfy the old string.** The argument is the feature; the string is the
  accident. Say which is which in the commit and the PR comment.
- Reproducing locally is one file in the test image:
  `docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest python -m pytest <file> -q -p no:cacheprovider`.

## 10. Repairing a red BOT PR (the fix-bot's own branch)

A `fix-bot`/`issue-bot` PR can be red on its own change. Treat it like any other PR, with four specifics:

- Check `--json headBranch,event` FIRST. A `pull_request` run on `fix/<x>` is not `main` being red, whatever
the user's wording — say which ref is red before diagnosing.
- **Reuse the branch's existing worktree.** `git worktree list` already has one per active branch; cd there
  instead of cutting a second worktree for the same branch (`git worktree add` refuses a checked-out branch).
- **Push normal commits to the fork head — never squash/amend** a branch a bot claimed and a reviewer may be
  reading (`bot-claim: fix-bot … run=<id>` in the PR comments). Rebase onto `origin/main` first, then
  `git push fork <branch>`.
- Post ONE PR comment: root cause (quote the assertion), the fix, the commit sha, the local test result. That
  comment is what a reviewer reads instead of the log. A test-only repair still updates the change record in
  the same push: the OpenSpec requirement/scenario naming the invariant, and the `agent-wiki/` entry.

## 11. Background CI watchers must not settle on an empty read

`gh pr checks <n>` occasionally returns no rows (not yet registered, transient API), so a loop that exits as
soon as `pending` is absent settles after one minute with nothing checked. Require at least one `pass`/`fail`
row before deciding, and print the rows on the settle path so the notification carries the verdict.
