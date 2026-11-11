---
name: upstream-contribution
description: "Use when filing issues/PRs for an upstream repo."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, issues, pr, upstream, contribution]
    category: software-development
    related_skills: [github, omarchy-contributing]
---

# Upstream Contribution (issues & PRs)

How to author well-formed, actionable issues (and later PRs) for an upstream repo
so a maintainer or the repo's own automation can act on them first try. The user
contributes to several upstream projects (Omarchy, llgenie, trending-local-llms),
so this is a recurring class of work.

## When to Use

- The user asks to file a feature request, bug report, or set of issues on a repo
  they do not own (an upstream project).
- The user asks to contribute a fix or feature to an upstream repo as a PR.
- The task is "create detailed issues for <upstream repo>" describing a feature
  that should be split into a parent + implementation issues.

## Procedure

1. **Locate the repo.** `gh search repos <name>` (or web search) to find the exact
   owner/repo. Clone it into the user's designated repo dir
   (`$HOME/repository/git/`), not the home folder.

2. **Read the repo's conventions BEFORE writing anything.** Read `README.md` and
   `AGENTS.md` (if present). They define the issue/PR contract: whether the repo is
   issue-driven (issue → feature branch → OpenSpec change → PR), whether it uses a
   `parent` / `impl(#N)` naming pattern, whether PRs must target upstream `main` from
   a fork, and what labels exist. Skipping this produces issues that don't fit the
   repo's workflow and get rejected or mis-scoped.

3. **Check for duplicates and labels.** `gh issue list --repo <o>/<r> --state open`
   and `gh issue list --search "<keywords>"` to confirm the feature isn't already
   filed; `gh label list --repo <o>/<r>` to tag correctly. Never file a duplicate.

4. **Ground each issue in the actual code.** Read the relevant source files (function
   names, CLI flags, data shapes, existing constants) so the issue names real symbols
   and real behavior. A vague issue referencing imagined APIs gets rejected; one that
   cites `scripts/detect_server.py::detect_backend()` and the real `data/models.json`
   shape is actionable. For a feature that consumes an external data source, read that
   source's contract too (e.g. the `data/models.json` shape of the index being wired in).

5. **Write each issue body to a file, then create with `--body-file`.** Long markdown
   bodies (backticks, quotes, newlines, JSON) get mangled by inline `--body "..."`
   shell escaping. Write to a scratch file and run
   `gh issue create --repo <o>/<r> --title "..." --label "..." --body-file <path>`.

6. **When the repo uses a parent/impl pattern, create the parent FIRST.** Capture its
   issue number, then create the impl issues with that real number in their titles
   (`impl(#92): ...`) and bodies. You cannot know the number until the parent exists.
   Split a large feature into one parent (overview, motivation, the impl list) plus
   one impl per independently-shippable piece, each with its own acceptance criteria
   and scope.

7. **Verify.** `gh issue list --repo <o>/<r> --state open` to confirm all issues
   landed with the right titles/labels.

## Pitfalls

- **Write long markdown bodies to files and use `--body-file`** — inline `--body` with
   backticks/quotes/newlines corrupts the body via shell escaping. This is the single
   biggest time-saver in this workflow. It applies to **every** write, not just
   `gh issue create`: `gh issue comment --body-file`, `gh pr edit --body-file`, and
   editing an existing comment via `gh api -X PATCH repos/<o>/<r>/issues/comments/<id>
   --input <file.json>` (a JSON file with a `body` key). Backticks in an inline body are
   executed as shell commands, silently dropping the text between them — the comment
   lands garbled with no error.
- **Create the parent before the impls** — impl titles must reference the parent's real
   number, which only exists after the parent is created.
- **Check `git remote -v` before pushing a PR branch — `origin` is not always the fork.** In a
  worktree cut from an upstream checkout, `origin` can be the upstream repo and the fork a second
  remote (`fork`). Pushing there puts your branch on the upstream repo and `gh pr create --head
  <you>:<branch>` fails with `GraphQL: … No commits between <upstream>:main and <you>:<branch>`
  (or `Head sha can't be blank`), because the head repo has no such branch. Fix: push to the fork
  remote by name (`git push -u fork <branch>`), then delete the stray branch you put on upstream
  (`git push origin --delete <branch>`) before opening the PR.
- **Read AGENTS.md/README first** — a repo's issue conventions (parent/impl, OpenSpec,
   PR-to-upstream-from-fork) are the contract; an issue that ignores them won't be picked
   up by the repo's automation.
- **Ground issues in real symbols** — name actual functions, CLI flags, and data shapes
   from the source; a feature issue that cites the real code is actionable, one that
   invents APIs is not.
- **Check for duplicates and available labels before creating** — filing a duplicate or an
   untagged issue wastes a maintainer's triage.
- **Keep all related work in ONE PR; never squash-merge; require a human approval.** The
   user wants every change for a feature set in a single PR (no stacked branches/PRs), the
   agent must not merge its own PR, and squash-merging is forbidden — the PR waits for a
   human reviewer. Record these rules in the repo's AGENTS.md so the contract is explicit
   and a future session starts already knowing them.

## References

- `references/issue-body-structure.md` — the sections a detailed feature issue carries
  (description, motivation, proposed solution, acceptance criteria, scope, context).
- `references/fork-sync-and-pr.md` — sync a fork's main to upstream, rebase the PR
  branch, open the PR with `gh pr create --head <you>:<branch>`, watch a CI run, and
  ship a docs-only follow-up PR after a feature that changed install/usage.
