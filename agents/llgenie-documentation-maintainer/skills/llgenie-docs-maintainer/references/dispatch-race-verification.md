# Reconciling a dispatch that raced an already-landed fix

A dispatch can arrive *both* behind and ahead of main, and either way the reported framing is a
claim about a branch, not about the tree. Never cut a branch or edit a doc row on trust.

- **Behind main:** the issue is already CLOSED and its fix merged by another vehicle — an owner-lane
  PR landing in the same minute the planner queued the dispatch. The dispatch's sha and its "needs
  this" framing are then both stale.
- **Ahead of main:** a peer lane reports a doc row is "stale since PR #X" — but PR #X is still OPEN,
  and that lane is reading its OWN branch head as the tip. On origin/main the doc is still accurate;
  it only goes stale the moment #X merges.

The reconcile below settles both: measure the tree at origin/main, never trust the sender's sha.

## Verify, in this order, before a worktree / branch / first edit

1. **Issue state** — `gh issue view <n> --repo asimov-agent/llgenie --json state,closedAt,title`.
   `CLOSED` (or a `closedAt` earlier than now) means stop and reconcile, do not implement.
2. **The closing vehicle** — `gh pr list --repo asimov-agent/llgenie --search '<n> in:body'
   --json number,state,title` and `git ls-remote origin 'refs/heads/*<n>*'`. Find the PR whose body
   says `Closes #<n>`; also catch a live branch another lane already claimed (#824 duplicate-race).
3. **The real tip** — `git fetch origin +refs/heads/main:refs/remotes/origin/main` (explicit refspec;
   never trust the local `origin/main` shadow), then compare `git rev-parse origin/main` to the sha
   the dispatch quotes. Main usually advances past it — a quoted sha is stale by the time it is read.
4. **Acceptance in a throwaway worktree** at origin/main:

   ```
   git worktree add --detach /tmp/wt-<n> origin/main
   cd /tmp/wt-<n> && make -s check-docs      # must print ok: ... and exit 0
   cd - && git worktree remove /tmp/wt-<n> --force && git worktree prune
   ```

   Read the landed note/trio content — confirm it names the correct PR number and merge sha and
   covers the behavioural change the issue describes. Measure, don't eyeball.

## If acceptance already holds

- Comment the evidence on the issue: issue closed at `<ts>`, closing PR `#<m>` merged as `<sha>`,
  `make check-docs` exit 0 at `<tip>`, note names the right PR/merge-sha.
- Report to the planner: "no new vehicle owed" — a duplicate re-opens nothing and burns a gate run.
- Never re-close the issue, never rebase or re-push the merged vehicle, never arm a duplicate (#1088).

### Prove it by real execution, never by manufacturing a change

When the work is already merged and a probe or a peer claims "no change attempted" / "not done",
**answer with executed evidence on the merged tip — do not invent a new branch/PR to look busy.**
That is the fabricated-completion failure: it touches files another lane owns and a green-looking
no-op PR reads as diligence while proving nothing.

- Prove the merge landed with the ancestor predicate and READ ITS EXIT CODE — `git merge-base
  --is-ancestor <merge-sha> origin/main && echo YES || echo NO`. **Never string-compare `git
  merge-base` output** (`[ "$(git merge-base $sha origin/main)" = "$sha" ]`): it prints nothing on
  error and several lines on a criss-cross base, so a genuinely merged commit reads as NOT-ancestor
  — a false negative that sends you re-doing landed work.
- Re-run the generator the change was about and show a **zero diff** (an in-sync `CHANGES.md`
  re-write prints no `git diff --stat` lines) — nothing left to write is the proof the mutation is
  complete.
- Run the pinned unit test the change was built for, in the hermetic test venv, and quote `N passed`
  (see `references/changes-index-maintenance.md` for the venv discovery command).
- Then state the verdict with the sha and the clock: merged commit is an ancestor of `<tip>`, gate X
  passes at `<tip>`, generator re-write is a no-op. That is a finished piece of work; the probe is
  stale, not the tree.

## If the report is ahead of main (an OPEN PR)

A peer says the row is stale because *their* PR changes the workflow. Do **not** edit the doc row:
the tree does not carry the change yet, so the edit would describe a change not in the tree and
falsify the doc against the current consumer.

1. Confirm the PR is unmerged: `gh pr view <m> --repo asimov-agent/llgenie --json state,mergeCommit`
   — `state: OPEN` and `mergeCommit: null` mean it is NOT on main. A head sha the peer quotes will
   fail `git merge-base --is-ancestor <head> origin/main`.
2. Read the consumer the doc row actually describes, at origin/main: e.g.
   `git show origin/main:.github/workflows/pipeline.yml | grep -n <target>`. If main still runs the
   old target, the row is accurate right now.
3. The doc row rides the PR that flips the workflow (same-PR rule): post the **exact replacement
   hunk** as a comment on that PR so it is visible and can be folded in at merge — do not open a
   parallel doc PR that lands ahead of it.
4. Protect the file: if it is gated from the peer's lane (agent-instruction / protected-write), the
   hunk in a comment is the handoff; land the doc as a companion only once the PR merges, never before.
5. Reply to the peer with the measured correction (main sha, the line that still runs the old
   target, `state=OPEN`), not a DM agreeing to "fix" a row that is not stale.

## If acceptance does NOT hold

The gap is real work: cut the branch from the freshly fetched origin/main sha, write it into the
first comment, and land the trio normally — still no merge/arm of the merged base (#1088).

## If the dispatch's done-definition contradicts the issue's own acceptance criteria

A dispatch is a **template** (`Done = ready-for-review PR that closes #<n> …`), and the template can
contradict the issue it dispatches. Measure the issue before building the vehicle; do not let the
template pick the shape for you.

- **"PR closes #<n>" against an issue whose own AC says the tracker STAYS OPEN.** A record-home /
  audit-tracker issue carries an AC like "this tracker stays OPEN across audits (close only when
  superseded)". A PR that `closes #<n>` directly reds that AC and ships a meaningless close. Such an
  issue is often all-behavioural: its AC are "stay open", "post the audit outcome here", "findings
  route through the queue" — none are PR-livable, and its body may already pass the six-section gate
  (`issue_body.missing()==[]`), so **no repo-file change is owed at all**. Verify by reading the AC
  list and checking the six-section headers; do not invent an edit to look busy.
- **A `closes #<n>` done-definition whose AC are already satisfied on main.** When the fix already
  landed (the code, its openspec change-dir, its test all present at origin/main), the docs deliverable
  is the durable-rule *note* (wiki + change-note + fleet bullet), not a re-implementation — but the
  close-line still needs the AC ticked with the on-main evidence.

When the template and the AC disagree, **post the contradiction on the issue and ask the dispatch
owner (the planner) for the ruling** — do not guess a vehicle, and do not build one that reds its own
acceptance criterion. A reconstructed done-definition in a PR body becomes a claim the board reads as
fact; asking is cheaper than a wrong merge. Claim the issue and cut the worktree first (so the claim
is durable), then hold the vehicle on the contradiction until answered.

## If the red is a stale base, not a stale dispatch

`check-pr-base` failing on an OPEN PR whose change is still valid means `origin/main` moved past the
cut sha — the base is stale, the change is not. Rebase, regenerate AGENTS:/BASE:/SYNC: at the new
base, force-push with lease, and judge the fresh head. Procedure and the gh/git field-name traps:
`references/base-race-rebase-and-metadata.md`.
