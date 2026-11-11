# Doing a work item in llgenie: issue → worktree → OpenSpec → PR → bots

Read this before starting any llgenie work item (a fix, a feature, an analysis issue you were asked to
implement). It is the order that keeps the artifacts pointing at each other, plus the traps that cost the
most time.

## 1. Look before you build

- `gh pr list --state all --search "<topic> in:title" --limit 15` plus `git worktree list` and `git branch -a
  | grep -i <topic>`: this repo accumulates one worktree and one branch per past attempt, and an abandoned
  branch often already holds most of the change. Reviving it is far cheaper than rewriting it. Revive with
  `git rebase --onto origin/main <old-base> <branch>`; when only the LAST commit of a multi-commit branch is
  still wanted, `git rebase --onto origin/main <that-commits-parent>` replays just it.
- Open the issue and read its comments: `<!-- bot-claim: <bot> <ts> ... -->` means a bot leg is implementing
  the SAME issue right now and will open its own PR. Do not silently duplicate it. Comment on the issue
  naming your PR, and check again before claiming done — the bot's PR may land first and close yours as a
  duplicate.

## 2. Read origin/main, not the local checkout

The user's checkout can be many commits behind, and then `grep`/`ls` in the repo root describes an OLD tree
(measured: a `ci.yml` job that had already been moved to its own workflow still looked present, which sent a
whole diagnosis down the wrong path). Read `git show origin/main:<path>`, or do all reading inside the
worktree you just cut from `origin/main`.

## 3. Remotes may be inverted — check before pushing

In this environment `git remote -v` can show `origin` = `asimov-agent/llgenie` (upstream) and `fork` =
`andyholst/llgenie`. "Push to origin" then creates the branch in the UPSTREAM repo. Rule: push the branch to
the remote whose URL is the owner's fork, delete the accidental upstream branch (`git push origin --delete
<branch>`), and open the PR with `--repo asimov-agent/llgenie --head andyholst:<branch>`.

## 4. OpenSpec is a container and writes as root

`make openspec-new NAME=<kebab>` creates the change directory as root-owned, so writing
`proposal.md` / `specs/<cap>/spec.md` / `tasks.md` answers `Permission denied`. Fix the ownership once:

```bash
sudo chown -R "$(id -u):$(id -g)" openspec/changes/<name>
```

Tick every task before pushing: `make ci-openspec` runs `openspec-tasks-check`, which fails on ANY `- [ ]` in
the change. A task that can only become true AFTER the merge cannot be a checkbox — word it as what the PR
actually delivers (e.g. "PR opened, with the bootstrap note explaining how the end-to-end proof is
obtained") instead of leaving it unticked. Every `#### Scenario:` carries a `- **Test:**` line naming the
exact `tests/test_*.py::test_case`.

## 5. Verify cheaply, then let CI do the long part

```bash
make test-image                                              # pull the hash-pinned test image
make lint check-docs check-workflows check-wiring             # seconds each, catches most pushes
make openspec-validate NAME=<name> && make openspec-tasks-check
docker run --rm -v "$PWD":/repo:rw -w /repo llgenie/test:latest \
  python -m pytest tests/test_<area>.py -q                    # the file you touched, seconds
make test-unit                                                # ~13 min locally, ~24 min on macos CI
```

Full CI on a PR is ~45–60 minutes (engine image builds + published-image tests). Poll instead of blocking:

```bash
gh pr checks <n> --repo <repo> --json name,state,bucket \
  --jq 'group_by(.bucket)[] | "\(.[0].bucket): \(length)"'
gh pr checks <n> --repo <repo> --json name,state --jq '.[] | select(.state=="FAILURE") | "FAIL \(.name)"'
```

`gh pr checks` answers "no checks reported" for the first minute after a push — that is not a missing run;
`gh run list --branch <branch>` shows the queued run.

**A red on ONE OS only, with the same head green on the other, is a live-network flake — not the diff.**
The macOS jobs run live-Hub and live-registry reads (`tests/test_engine_skills.py`'s digest lookup, the
top-tier acceptance dry run), so a macOS-only red with `linux / unit` green on the SAME sha is a network
read that returned nothing. Re-run just the failed job (`gh run rerun <id> --repo <repo> --failed`) before
debugging the change, and do not hand it to a repair bot as a code defect: a repair runner on Linux cannot
reproduce it, so the loop discards the attempt.

## 6. Commit and PR

Set the identity the author gate accepts before committing (`git config user.name "Asimov Agent"`,
`git config user.email support@docondee.com`, or the Andy Holst identity when that is the account in use).
Write the commit body with `Issue:` / `Fix:` / `Benefit:` / `Technical:` parts and the issue reference — the
hygiene gate reads it. The PR body ends with `closes #<n>` when it implements the issue, and a PR that fixes
a `workflow_run`-triggered gate CANNOT merge itself (the runner executes the default branch's copy), so say
that in the PR before a reviewer asks why auto-merge failed on it.

## 7. Why the issue bot ignores the issue you expect it to implement

The implementer's queue is **label-driven**: it lists `--label agent:implement`, then `--label agent:ready`,
and nothing else. So an issue can be perfectly valid and still invisible.

- A hand-filed canonical issue usually carries NO label; the reactor-filed copies do. When the bot keeps
  closing copies as "duplicate of #N" and never implements #N, label #N (`gh issue edit N --add-label
  agent:implement`) — that is the whole fix from the operational side.
- `agent:refined` and `agent:closed` are the DECIDED labels: the picker skips any issue carrying either. A
  refine verdict therefore PARKS an issue forever. To get a refined issue implemented, remove
  `agent:refined` and add `agent:ready`, then let the next run pick it.
- A run that picks a duplicate produces no PR at all (verdict `close`) — "no PR from the issue bot" is a
  verdict, not a broken bot. Read the run's outcome line (`verdict=close|refine|implement`) before
  diagnosing anything else.
- Which bot re-added a label you removed is answerable: `gh api
  repos/<repo>/issues/<n>/events --per_page=30 --jq '.[] | select(.event=="labeled" or
  .event=="unlabeled") | "\(.created_at) \(.event) \(.label.name) by=\(.actor.login)"'`. Do this before
  concluding the label edit "did not take".

## 8. Analysis findings are issues, never extra code

While implementing, file each real gap you notice as its own detailed issue (evidence, why it matters, what
"done" looks like) and link it both ways from the PR's `Not covered`. Do not fold a second objective into
this PR.
