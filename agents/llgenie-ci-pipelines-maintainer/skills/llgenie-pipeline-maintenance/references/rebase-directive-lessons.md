# Owner rebase directives on this lane's own PRs

An owner instruction to "rebase my PRs onto the new main tip <sha>" is this lane's own vehicle work
(the standing "never rebase" rule hands OTHER lanes' PRs to `llgenie-pr-merge-conflict`; it does not
forbid this lane refreshing its own pipeline-fix PRs when the owner says so). Procedure and traps:

## 1. The named sha may be an ANCESTOR of the true tip

A directive quotes the merge sha the sender last saw. `upstream/main` usually advanced since.

```
git fetch upstream main && git rev-parse upstream/main    # the ACTUAL tip
```

Rebase onto the fetched tip (the named sha is then included by descent), and report the sha you
rebased onto — the true tip, not the quoted one. Say both if they differ, so the sender can follow.

## 2. A rebase clears only BASE-DEPENDENT reds

Before rebasing, classify the red by reproducing it locally at the current head:

```
make check-pr-base            PR_BASE=upstream/main PR_HEAD=<head>
make check-pr-openspec-change PR_BASE=upstream/main PR_HEAD=<head> PR_BODY=<live-body-file>
make check-pr-acceptance      PR_BASE=upstream/main PR_HEAD=<head> PR_BODY=<live-body-file>
```

- `check-pr-base` failure = base staleness → the rebase is the fix.
- `check-pr-openspec-change` failure on a product-code PR = no `openspec/changes/<name>/` in the diff
  and no `OPENSPEC: <name>` body line. **Base-independent** — the rebase cannot clear it. Fix it:
  `make openspec-new NAME=<change>`, write `proposal.md` / `tasks.md` / `specs/<name>/spec.md`, add the
  `OPENSPEC: <change>` body line with `gh pr edit --body-file`, re-run the gate to `OK`.
- `check-pr-acceptance` failure naming an unticked criterion = the reviewer's verdict-gated write-back
  (#1644). Not base-related and not this lane's to self-tick — post the exact violation on the PR and
  route it to the reviewer.

So after a rebase, re-run the same three gates; do not report "rebase done, red cleared" until the
gate itself returns rc=0 at the new head.

## 3. Prove from the gate, not the badge

The guard job's `/actions/jobs/<id>/logs` endpoint can return a ~60-byte stub pointing at a redirect.
The reliable evidence is the local make target (above): its rc and its own violation text. Quote both
in the report, plus the head sha and the run id.

## 4. Root-owned openspec scaffold dir

`make openspec-new` (and the container-backed targets) create files as uid 0. Author the files in the
scratch dir and copy them in:

```
docker run --rm -u root -v "$SCRATCH":"$SCRATCH":ro -v "$PWD":/repo:rw -w /repo \
  llgenie/test:latest bash -c 'mkdir -p /repo/openspec/changes/<name> && cp "$SCRATCH"/*.md ...'
```

Git reads root-owned files fine, so the commit is unaffected; the dir must be writable again before a
later container edit, so keep the copy step idempotent rather than hand-chowning from the host.

## 5. Worktree hygiene

- Fetch the branch, then `git reset --hard <remote>/<branch>` so you move the ACTUAL PR head, not a
  stale local commit that diverged while the remote was force-pushed by another lane.
- Untracked unrelated files survive reset and rebase — leave them, never tidy another lane's residue.
- Push with `--force-with-lease --force-if-includes` after fetching.
- If a commit lands with a damaged file (an interrupted in-place edit), repair rather than stack:
  stage the good file, prove the committed blob is the good one (`git show :<path> | wc -l`), amend,
  force-push, and read the remote ref back (`remote == local`) before calling it done.
