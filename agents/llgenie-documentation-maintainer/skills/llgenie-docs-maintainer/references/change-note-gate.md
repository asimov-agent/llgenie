# The change→note gate (#1123) and how a docs PR's CI reads

## `docs/` IS a notified surface — the common false conclusion

`scripts/check_docs.py` matches notified surfaces against `NOTE_SURFACE_RES`, and that regex list
**includes `^docs/.*\.md`**. Only the repo-root `README.md` is *not* a notified surface. So a PR that
edits `docs/BOTS.md`, `docs/ARCHITECTURE.md` or any other `docs/*.md` owes the full trio:

1. `agent-wiki/<stem>.md` — a real note (frontmatter + body), naming the issue it came from.
2. `docs/changes.d/<stem>.md` — one row in the form
   `| YYYY-MM-DD | summary | [<stem>](agent-wiki/<stem>.md) | #<issue> |`
3. `CHANGES.md` regenerated from the fragments via `make changes-index` (the fragment is not indexed
   until you regenerate).

Do not reason "it's only docs, no note is owed" — that conclusion reds the `scope` job in ~17s with a
message naming the changed docs file. When in doubt, grep the check for the surface list before asserting
the gate is satisfied.

Trap seen in practice: the note/fragment written but left **uncommitted**, then the gate re-run — the
gate diffs `origin/main...HEAD`, so staged-but-uncommitted files are invisible and it still fails.
Commit the trio, then re-run.

## Local green ≠ CI green (the trap that cost a cycle)

`make -s check-docs` on a working tree and CI's `scope` job answer different questions:

- Local: the gate runs against whatever is in the tree, with no diff to a PR base.
- CI: the gate runs `origin/main...HEAD` and fails if the committed branch changes a notified surface
  without the matching note/fragment/index row.

Therefore **never report "gates green" / "PR done" from local `make` runs alone.** The claim needs the
PR's own check rollup at the pushed head. Sequence: commit → push → read `gh pr checks <n>` /
check-runs API at that exact head → only then report.

## Reading PR state for a docs-only diff

- `mergeStateStatus: BLOCKED` with **all** check-runs green is normal for a docs-only PR: `ci.yml`'s
  required jobs never start (the scope workflow `paths-ignore`s docs-only diffs), so a required check
  reads as never-completed. It is an artifact, not a red. Confirm by reading the per-check API, not by
  trusting the enum. A real hold is a `do-not-merge` label — check `labels` separately.
- Trust the **direct API read** (`/commits/<sha>/check-runs`) over any derived summary line a polling
  script prints. A loop that classifies checks itself can emit a self-contradictory verdict on a
  transient API hiccup; the raw `status`/`conclusion` fields are the fact.
- Record the head sha with every green claim. A green taken before a force-push is a claim about a
  branch that no longer exists.

## Auditing change-note coverage: read the tree at the audited sha, not a worktree

To audit whether merged PRs carry their note + `changes.d` row + `CHANGES.md` index, measure the
**audited sha's tree**, never a worktree checked out at some other head. A worktree parked on a stale
branch (e.g. an old PR branch) shows that branch's `docs/changes.d/` and `CHANGES.md`, so `grep`/`ls`
against it returns wrong counts — often all-zero for rows that are present and correct on main.

- List and read files at a ref without checking it out:
  `git ls-tree -r --name-only <sha> docs/changes.d/`, `git show <sha>:CHANGES.md`, and
  `git grep <stem> <sha> -- docs/changes.d`. Do this at the fetched `origin/main` tip.
- The merge window comes from `git log --oneline origin/main`, **not** `git log --merges`: recent PRs
  land as squash commits with one parent, so `--merges` lists only ancient true-merge PRs and silently
  omits every squash-merged one you meant to audit.
- A clean audit's evidence is the gate itself passing at that tip in a scratch worktree cut at the sha
  (`git worktree add /tmp/audit <sha>` → `python3 scripts/check_docs.py check` rc=0), then remove it.
  Report "re-audited at <sha>, no findings" with the sha; a count with no sha is a claim about a tree
  that may already be gone.

## Claim-read only a freshly-fetched canonical tip — never a tip measured earlier in the session

A main-tip sha quoted from an earlier fetch is “stale by the time another lane cites a newer tip.”
Seen in practice: a README restore was reported “still missing” from `69b86b3b` (a tip fetched
earlier), when the canonical remote had since grown and the restore PR (#1635, `56d5e517`) was already
on main at the true tip `56ed9a80`. Before asserting a claim about main (“this clause/drop/count is
present/absent”), `git fetch origin +refs/heads/main:refs/remotes/origin/main` and re-read the exact
target at the fresh tip. When a lane hands you a newer tip sha, re-measure your claim against it
instead of arguing the stale one.

A restore/fix is not owed if it already landed: an issue marked CLOSED/COMPLETED whose closing PR
carries the exact acceptance criteria is done — do not file or route a duplicate even when an earlier
read suggested the gap was open; re-check state + tip first. Check `gh issue view <n> --json state`
and `git merge-base --is-ancestor <pr-commit> origin/main` before treating something as outstanding.

## When the rebase is needed

`origin/main` moves between branch-cut and push. Rebase only when the PR is `CONFLICTING` or its base
merged — but always fetch `origin/main` first and re-run the gates after the rebase, because the
three-dot diff basis changed.
