---
name: llgenie-pr-rebase
description: Use when a conflicting llgenie PR needs a rebase.
version: 1.0.0
author: llgenie-pr-merge-conflict
license: MIT
metadata:
  hermes:
    tags: [git, rebase, github, llgenie]
    related_skills: [github, pr-finalization]
---

# Rebase a conflicting llgenie PR

## When to Use

Use when a pull request in `asimov-agent/llgenie` shows `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` or `BEHIND`, and it must be brought onto the current `main` tip while staying a single reviewable commit.

Repo: `asimov-agent/llgenie`. Two checkouts matter: the owner's clone (never edit it, never `git switch` it) and your own worktree root beside it (`../llgenie-wt/<n>`).

## Inputs

- The open PR list with `mergeStateStatus`, so the CONFLICTING / DIRTY subset is named, not guessed.
- The owner's clone and your own `../llgenie-wt/<n>` worktree root — never the owner's checkout.
- `origin` (asimov-agent) refs: `main` and the head branch, fetched as `refs/remotes/origin/<head>`.
- The resolve-and-stage half: **`.hermes/skills/rebase-conflict/SKILL.md`** — named here as the dependency, never restated. It resolves the conflicted files, stages them (`git add`), and stops; `git rebase --continue` and the push are the caller's.

## Output

- The head branch re-based onto `origin/main` as ONE reviewable commit, the original author preserved, pushed back to `origin` (asimov-agent) with `--force-with-lease="refs/heads/$BR:origin/$BR"`.
- The read-back report: `HEAD` == `origin/$BR` and parent == `origin/main`, plus `mergeable`/`mergeStateStatus` and checks from the API — never assumed.

## 0. Hand off first
Message the owning bot via `message_agent` before touching the branch — `@llgenie-issse-implementer` for issue-bot PRs, `@llgenie-ci-pipelines-maintainer` for CI, `@llgenie-documentation-maintainer` for docs. Only proceed when they decline or a coordinating bot (e.g. `@llgenie-planner`) hands it over.

## 1. Survey
```bash
gh pr list --repo asimov-agent/llgenie --state open --limit 100 \
  --json number,title,headRefName,baseRefName,isDraft,mergeable,mergeStateStatus
```
`mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` are the ones to rebase. `MERGEABLE` + `BLOCKED` means waiting on checks/approval — do not rebase those.

A conflicting PR reports **no checks at all** ("no checks reported on the … branch") because GitHub builds no merge ref. That is the symptom, not a broken workflow.

If this procedure is scheduled, gate it on a deterministic detector whose whole output is the conflicting subset: an unchanged hour then produces no agent run and no delivery, and "alert only on a transition" is enforced by construction rather than by prompt discipline. Two properties are not optional — the detector must report a hard error (never "nothing conflicting") when the GitHub read itself fails, or the watch has a silent blind spot; and a direct/forced run bypasses the gate, so only a scheduled tick proves suppression.

## 2. Worktree (never the owner checkout)
```bash
cd <owner-clone>  # the checkout you were told never to edit
git fetch origin main
git fetch origin '<head-branch>:refs/remotes/origin/<head-branch>'
git worktree add -b pr<N>-rebase ../llgenie-wt/pr<N> origin/<head-branch>
```
Branches of agent PRs live in the **base repo**, not the `andyholst` fork. Push back to `origin` (asimov-agent), not `fork`.

## 3. Rebase
```bash
cd ../llgenie-wt/pr<N> && git rebase origin/main
```
Read `AGENTS.md` at the target main sha before the first edit.

## 4. Resolve — know the two habitual conflicts
- **`CHANGES.md`** is an index table, newest first. Two branches almost always add a new top row at the same position. Resolution is **keep both rows** — main's existing row stays where main has it, the branch's new row goes directly under it. Never drop either row: `make check-docs` fails on a note with no row *and* a row with no note. Same-date rows may sit in either order.
- Engine/docs registries (`README.md`, `docs/ARCHITECTURE.md`) resolve toward **main's** version; do not invent a third behaviour inside a rebase.

If the conflict is a genuine redesign rather than a re-apply, stop and report instead of redesigning.

Keep the branch at **one commit**. Author must remain `Asimov Agent <support@docondee.com>` or `Andy Holst` — a rebase preserves the original author; never re-author.

## 5. Gates before push
```bash
make check-docs
make openspec-validate NAME=<change-name>
docker run --rm -u root --network host -v "$PWD":"$PWD":rw -w "$PWD" llgenie/test \
  python -m pytest tests/test_<touched>.py -p no:cacheprovider -q
```
`make test-unit` is the full gate but slow (~10 min); the targeted container run gives the same signal in seconds and does not depend on the host having pytest.

## 6. Push
```bash
BR=<head-branch>
git push --force-with-lease="refs/heads/$BR:origin/$BR" origin "HEAD:refs/heads/$BR"
```
Lease on the ref you actually fetched, or the push is rejected. Verify: `git rev-parse HEAD` == `git rev-parse origin/$BR`, and parent == `origin/main`.

## 7. Report
Read back, never assume: `gh pr view <N> --json headRefOid,mergeable,mergeStateStatus` and `gh pr checks <N>`. Optionally post the rebase note as a PR comment and re-read it via the API.

## Rules

- **Never merge, never squash to `main`, never push to `main`** — merges are CI/owner only (#1088).
- **The split is the contract.** The inner half (`.hermes/skills/rebase-conflict/SKILL.md`) runs in the CI image as a leg that resolves, stages and stops at `git add` — it must never be restated here. This outer half runs on the host and owns the survey, the worktree, the having-gate, the lease and the report. Never merge the two contracts: one would then say "stop after staging" and "survey and push" at once.
- **One commit, one author.** Author stays `Asimov Agent <support@docondee.com>` or `Andy Holst`; never re-author a rebase.
- **Kill by PID, never by pattern** — `pkill -f 'make test-unit'` matches the shell running that very command. Capture the PID and `kill <pid>`.
- A container suite printing nothing 18 minutes past its timeout is not "slow": kill it and run the bounded subset.
- **Never touch unrelated files**; a rebase PR's diff stays its own change.
- **Never run `make worktree-prune` / `git worktree prune` / `git worktree remove`** — owner-only; leave the worktree for the owner to inspect.

## Hard rules
- Never merge, never squash to `main`, never push to `main` — merges are CI/owner only.
- Kill by PID, never by pattern: `pkill -f 'make test-unit'` matches the shell running that very command and takes down the call instead of the target. Capture the PID (`$!`, or `process_manage list`) and `kill <pid>`. Same class of mistake as a `git checkout --` that eats someone else's edit.
- A container suite that prints nothing for 18 minutes past its own timeout is not "slow, nearly done": kill it and run the bounded subset. The targeted `llgenie/test` pytest gives the same signal in ~1 s.
- Never touch unrelated files; a rebase PR's diff must stay its own change.
- Never run `make worktree-prune` / `git worktree prune` / `git worktree remove` — owner-only; it deletes directories and cannot see uncommitted work.
- Leave the worktree in place for the owner to inspect.

## Pitfalls
- A sweep that reports success while PRs stay conflicted, or crashes its own decision step, is broken — check the run log, do not trust the green.
- CI `guard` sitting `pending` for many minutes with other runs also queued is a **runner capacity** problem, not something wrong with the PR. Report the run ids and say so; do not re-push.
- Capacity starvation and a crashing automation sweep are different failures: keep them in separate issues. Conflating them hides one behind the other.
- After a long capacity backlog clears, PRs that were `MERGEABLE` are the ones to watch: `main` moved while nothing merged, so they can turn `DIRTY` and need this same rebase.
- Worktree count is a tracked trend under an owner-only prune. Always report the worktree you left and its path; never prune to compensate.
- The `pr<N>-rebase`-style local branch is scratch; the branch that matters is the one on `origin`.
- The knowledge here belongs in the repo, not only in this profile: a host skill is admitted **by name** in `HOST_SKILLS` (`scripts/check_agent_skills.py`) and needs frontmatter plus `## Inputs`/`## Output`/`## Rules`. `.hermes/skills/rebase-conflict` already covers the inner half (resolve, stage, stop, caller continues and pushes) — any in-tree version of this procedure must *point* at it, never restate it, and must say which half runs where: the leg contract stops at `git add` in the CI image, this outer procedure owns survey, worktree, gates, lease and report on the host. Never merge the two contracts: one would then say "stop after staging" and "survey and push" at once.
- When filing an issue whose `## Technical` embeds a whole `SKILL.md`, the body gate (`scripts/issue_body.py::missing`) reads every `^## ` line as an issue section: a verbatim fence yields "unknown sections" and `Technical` stops being last. Demote the embedded headings to `###` and tell the implementer to restore `##` when writing the file.
- Rebase `--force-with-lease` leases must name the ref actually fetched, else the push is rejected; verify afterwards that `HEAD` == `origin/<branch>` and the parent is `origin/main`.
