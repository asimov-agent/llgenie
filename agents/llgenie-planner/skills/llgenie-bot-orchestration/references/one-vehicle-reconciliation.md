# Reconciling two live PRs for one issue

When a lane opens a second PR for an issue that already has a designated vehicle (the standing
one-vehicle rule), the conflict is yours to resolve — not the lane's to keep carrying. Do not let a
third PR appear while you decide.

## Procedure

1. **Confirm the violation.** `gh pr view <a> --json headRefName,headRefOid,baseRefName,state,body`
   and the same for `<b>`. Two OPEN PRs whose bodies both `closes #<issue>` = two vehicles. Check
   ancestry: `git merge-base --is-ancestor <headA> <headB>` — if false, they are divergent siblings
   (neither supersedes the other), not a stack.
2. **Measure merit side by side.** For each: `base.sha` (`gh api repos/.../pulls/<n> --jq '.base.sha'`)
   vs the current `origin/main` tip; `mergeable` / `mergeStateStatus`; the file set
   (`gh pr diff <n> --name-only`); and the added tests (`gh pr diff <n> | grep '^+def test_'`).
   A PR missing the repo-mandated doc trail (CHANGES.md + `agent-wiki/<stem>.md` +
   `docs/changes.d/<stem>.md`) cannot merge under the repo's own norms — that alone usually decides it.
   Stale base is a rebase, not a content gap: freshness alone rarely outweighs a doc-trail gap.
3. **Pick one, close the other — unless the loser may be the owner's own work.** Prefer the vehicle
   already designated on-record (and the one with the doc trail + the fuller test set). Before you
   close anything, ask: *could this PR be the owner's own deliberate change?* If the loser carries
   scope that is neither the issue's dispatch scope nor a lane's plausible slip (e.g. it removed a
   just-merged doc note and re-pointed a file no dispatched lane touched), it may be the owner's work.
   **Then do not close it yourself.** Post the measured comparison on the issue, state which vehicle is
   canonical and why, and surface the disposition as a question to the owner (a `clarify` if they are
   in-session, otherwise an issue comment naming the exact choice). Closing the owner's own PR on your
   own authority is out of remit even when the comparison is decisive. Once the owner rules, close the
   loser with `gh pr close <n> --comment <table>` where the comment is a markdown comparison table
   (base.sha, mergeable, docs present?, test count, impl equivalence, per-file scope diff) AND an
   explicit line: *the diagnosis is NOT rejected — this is a vehicles decision, not a diagnosis
   reversal.* Verify: `gh pr view <n> --json state` → `CLOSED`.
4. **Redirect the lane onto the survivor.** The redirect must state: keep ONE branch, do not open a
   third PR; rebase to the freshly-fetched `origin/main` sha (name it); keep the doc trail; carry every
   acceptance behaviour the closed PR had; re-target any CI watcher to the survivor's head; arm per the
   repo's arm protocol only on all-green, reading `autoMergeRequest` back.
5. **Deliver the redirect on-record, not only by DM.** `message_agent` can return `queue_full`
   ("Do not resend"). When it does, the durable channel is a comment on the SURVIVING PR
   (`gh issue comment <pr> --body-file`) — the lane reads its active PR. Quote the decision there so a
   queue-full DM does not strand the instruction.

## Pitfalls

- **Commit author is not an identity proxy.** Do not infer "owner-authored vs lane-authored" from
  `git log --format=%an` — every lane pushes with the same bot identity, so all candidates show the
  same author string. The only evidence that distinguishes them is scope (per-file diff vs the
  dispatch) plus the PR creator/timeline actor; measure that, do not read the commit author.
- **`gh pr close` answering "already closed" (or a merge already in place) is a concurrent actor, not
  an error.** Check `/issues/<n>/timeline` for the `closed`/`merged` event and its actor before
  treating it as a failure or an incident — the owner acts in real time alongside the pass, and their
  close/merge is a legitimate ruling. Attribute it, then re-verify against the resulting state.
- **A closed duplicate is not a rejected diagnosis.** Say so in the close comment, or the next reader
  reopens the argument instead of the consolidation.
- **Never pick on freshness alone.** A fresh base with no CHANGES/wiki/changes.d loses to a stale base
  that has them; the rebase is cheap, the missing doc trail is a gate red.
- **Do not report "two PRs, chose one" as done** until the lane's CI watcher points at the survivor —
  a watcher still armed on the closed head arms nothing and reports green on a dead branch.
