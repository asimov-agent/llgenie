---
name: github-issue-tree
description: "Use when planning a project as a GitHub issue tree."
version: 1.0.0
---

# Plan a project as a linked GitHub issue tree

Turn a multi-stage feature/plan into a trackable issue tree: one parent, sub-issues, `blocked_by` ordering, and bodies that cross-reference the real issue numbers. The core problem is that issue numbers don't exist until you create the issues — so you cannot write `#97` inline in a draft.

## Procedure

1. Draft each issue body as a file in scratch, one per issue. Put cross-references as CAPITALIZED placeholders (`{TOKEN}`, `{SKILLS}`, `{PROV}`, `{DRIFT}`) and keep a map `{PLACEHOLDER: meaning}`. Never `{placeholder}` and never a number you don't have yet.
   For a **parent + children tree**, use `#CHILD1..#CHILDn` as the placeholders: the parent's index lists them, and each child body opens with a `Parent: #<parent>` line. After creation, substitute the real numbers everywhere (parent index AND each child body) in one pass — a child that still says `#CHILD3` after the parent is fixed is a broken link a reviewer will catch.
2. Create all issues first via `gh issue create --body-file`. Capture the returned numbers.
3. Batch-substitute the map into every draft file (python `str.replace` loop), then render one placeholder-free final per issue.
4. Set titles and bodies with `gh issue edit N --repo OWNER/REPO --title '...' --body-file N.md`. Prefer `--body-file` over inline `--body` (shell quoting on long markdown). Pipe the whole batch `</dev/null` so `gh` never drops into its interactive editor.
5. Link the tree via `gh api` REST (the one place `gh` porcelain lacks these endpoints). Two shapes:
   - Parent → sub-issues: `POST /repos/{o}/{r}/issues/{PARENT}/sub_issues` with `sub_issue_id=<NODE_ID>`.
   - Ordering: `POST /repos/{o}/{r}/issues/{ISSUE}/dependencies/blocked_by` with `issue_id=<NODE_ID>`.
   - `gh api` needs the GLOBAL database ID (from `gh api repos/{o}/{r}/issues/N -q .id`), not the issue number.
6. Superseded old issues get closed `--reason "not planned"` with a comment naming the new parent + what changed, so the history explains the decision.
7. **Link bidirectionally, not just parent→child.** The parent names every child; every child carries a `Parent: #N` line; and an EXISTING issue that already tracks part of the story gets a short comment naming the parent and stating why it is a sibling, not a duplicate. A tree whose children point up but whose parent index omits one is half-linked.
8. **House style for finding/audit trees** (a repo whose AGENTS.md mandates `Not covered` sections and demonstrable findings): each child body carries a measured `$ …` evidence block (grep/wc/line numbers, not prose), an `Acceptance` list with a test name, and a `Not covered` section that files each deferred item as its OWN linked issue — never prose. Keep the parent's index wording and the child's title IDENTICAL; a parent that says "every leg refuses" while the child title says "only the smoke refuses" reads as two different claims.
9. Read back everything before claiming done: states, sub-issues list, `blocked_by`, and each body. The user treats no-mutation / partial-substitution claims as suspect until fresh reads confirm.

## Delivering the tree (parent + implementation in one request)

When the request is "create the issue, split it into sub-issues, then complete it all and open the
PRs", the tree is step 0, not the deliverable:

1. Create and link the whole tree FIRST, read it back (step 9), and only then start work. The issues
   are the checklist of record while you implement, so they must exist before the first branch.
2. Work **one child at a time, in `blocked_by` order**: its own worktree off the fresh default
   branch, its own OpenSpec change (if the repo uses one), its own PR that `closes #<child>`.
   Touching two children in one branch makes each PR unmergeable on the other's gate failures.
3. Do not reopen a child that a dependency has not landed yet — say it is blocked instead. A child
   whose prerequisite PR is still open can still be built, but its PR must not claim the dependency
   closed.
4. Each PR body repeats the child's own goal (Issue / Fix / Benefit / Technical) — the reviewer must
   not have to open the tree to understand the diff, and the parent issue must not be closed by a
   child PR.
5. Budget the full gate honestly: a repo whose unit suite runs 10+ minutes per branch is 10+ minutes
   per child. Run the suite once per child in the background while preparing the next child's files,
   and never report a child done on a suite you did not actually see finish.
6. **A child that needs an unmerged sibling's files is STACKED, not blocked.** Cut its branch from the
   parent's branch (`git worktree add -b feat/child … feat/parent`), open the PR against `main`
   anyway, and make the body's first line `**Stacked on #<parent>** (…)`. Review order goes in the
   body: earlier PRs first. When the parent lands, `git rebase origin/main` on the child drops the
   parent's commits by itself — no cherry-pick, no hand-editing.
   Rebasing a stacked child onto `main` BEFORE its parent lands is the one thing that breaks it: the
   parent's files vanish and the branch stops building. Check with
   `git merge-base --is-ancestor origin/main HEAD` (true = at/after main) and rebase the stack
   parent-first, never top-first.
7. **Fix a defect found by a child on the branch that owns the file, then propagate.** A CI or gate
   failure in `security_scan.py` belongs to the child that introduced it; commit there, then
   `git rebase` the descendants onto the new tip. A fix committed only on the top branch leaves the
   intermediate PRs red, and a `git diff`-based patch moved between worktrees does not apply when a
   descendant has added lines in the same file — apply it with
   `git apply --exclude=<conflicting file> …` and edit that one file in place instead.
   If the patch still refuses to apply to the ancestor (its context carries a descendant's edits),
   do NOT force it: keep the refactor as its own commit on the branch where the files ended up and
   say so in the bodies of the PRs whose diff it also touches. A disclosed add-then-remove across a
   stack is reviewable; a broken intermediate branch is not. Verify the applied result, never the
   intent: a patch that half-applied leaves the branch red on files you did not touch.
8. **Landing is not the agent's job.** In a repo whose branch protection requires a review, the
   deliverable is "reviewable PR": every head at/after `origin/main`, checks green, body complete.
   Verify the push landed (`git ls-remote origin refs/heads/<branch>` == local `rev-parse HEAD`) and
   report the PR URLs — do not wait, re-push, or merge to clear `BLOCKED`/`REVIEW_REQUIRED`.
9. Close the loop in the tracker once the PRs exist: one comment per child naming its PR, and one
   comment on the parent listing child → PR → what lands, so a reader never has to walk the tree.

## Pitfalls

- A substitution pass is not atomic. When a script substitutes then asserts, files written before the assert still land changed. Verify by re-globbing and re-reading, and never let a mid-loop `assert` record success — do the assert on the final state, not alongside the write.
- `gh api .../sub_issues` and `.../blocked_by` both return arrays; query with `-q '[.[].number]'`, not `.number`.
- When scanning a body for issue refs, `scan("#3[0-9][0-9]")` returns a STRING, so piping it into `.unique` fails with `unique cannot be applied to: string`. Wrap the scalar in an array first — `[.body|scan(...)]|unique` — or use `split("\n")|map(select(test(...)))`. Same rule for any jq scalar piped into an array function.
- Reuse a closed/superseded issue by closing the OLD one and pointing its sub-issues/deps at the NEW parent; don't reopen old threads into the new plan.
- Log EVIDENCE_ADDED and read back after remote mutation rather than re-running the mutating task to satisfy a supervisor's transcript scan.
- **A scope change discovered mid-implementation belongs in the tree, in the same batch as the code.** When a component is dropped or a requirement reinterpreted, comment on every affected child AND the parent with what changed and why, and update the OpenSpec/proposal + docs that stated the old scope. A tree whose issues still describe a component the PR removes is a contradiction reviewers read as drift, not as progress — and repos that mandate issue↔spec↔code agreement treat it as a workflow defect.
- A gate that has never been run against a *broken* input is not known to be a gate. Prove it: run it on the untouched default branch (must fail, naming every offender), then on the fixed branch (must pass).
