## Your own rules are a repo artifact

A host agent's `SOUL.md` and skills live outside version control by default, so an instruction change is the one
behaviour change nobody reviews — and the host agents hold the write credentials. Any change to this skill or to the
planner's `SOUL.md` goes through an llgenie issue and a PR that commits the text under `agents/<profile>/` (issue
#791 is the tracking issue and the layout). File the issue first, dispatch the PR, then sync the profile from the
repository; never edit the live `SOUL.md` and stop there.

**Filing the trail issue is half the mutation; dispatching the owning lane is the other half.** A trail issue
carrying a `bot-claim:` comment that *names* the owning lane is board state, not moved work — the lane does not read
issue bodies on its own and will sit idle while the versioning debt stays un-landed. After `gh issue create` +
claim, `message_agent` the owning lane (skill/doc files under `agents/<profile>/` → the documentation-maintainer
lane) with the issue ids, the preflight (fresh `origin/main`, read `AGENTS.md` at that sha, name it in the PR body),
fold-one-vehicle instruction, and never-merge. Treat "issue open + claim posted" as done only once a lane dispatch
exists; a filed-but-undispatched trail is the same idleness defect as a filed-but-unassigned issue.

**Validate a live edit is genuinely tree-absent before filing its trail.** Before opening a #791 issue for a rule
you just wrote into the live profile, prove the tree copy lacks it: `git show origin/main:<skill.md> | grep -c
'<distinctive phrase>'` must read `0` while the live file reads `1`. If the tree already carries the text, the
"trail" is a phony duplicate against a merged rule, and the honest disposition is "already versioned at `<sha>`,
no issue." One live edit → one trail issue; when a single session touches several bullets, each distinct lesson
gets its own trail (do not silently fold a dispatch-race guard and a close-audit rule into one issue whose body
names only one of them).

**A rule learned by one lane must reach every lane, and verbatim.** When a session produces rules the whole fleet
needs (destructive-action prohibitions, reporting shape, freeze semantics), file **one** issue carrying the rules as a
single canonical block, then send every active profile the same instruction: copy the block *verbatim* under one
heading, and add **one lane-specific rule the canonical text cannot express** (the reviewer's "retract in the PR, not
in a DM"; the rebase lane's "one push per PR then freeze"; the CI lane's "authorised is not now"). Verbatim matters
because the profiles are then diffable against each other — paraphrases drift within a week and each lane ends up
with a subtly different fleet.

**Prove the copy, do not assert it.** Each profile PR should show `block in soul` computed from the issue body (extract the block, test membership) rather than "copied verbatim", and the profile gate should be run with a **negative control** — delete one canonical rule and watch the gate red with a message naming the missing rule, restore, re-run green. A profile SOUL is a protected agent-instruction file: an approval prompt that times out is escalated in one line naming the file and the reason, never worked around with a heredoc or `cp`.

**The canonical block grows after the copies are opened, so re-diff at merge time.** Rules are added while profile PRs are already in review, which silently makes every earlier copy stale: the issue body is the source of truth and the PR is a snapshot of it. Before approving or merging any copy, diff the artefact against the current body — extract the block, assert membership, and compare byte counts and bullet counts (`<n> bytes · <n> bullets`). A copy showing 1758 bytes / 10 bullets against a 2137-byte / 11-bullet body is *not* "verified in #<issue>", it is one rule behind, and merging it ships a SOUL missing the rule that lane earned. Hold the merge, put the hold as a comment on the PR so the owner sees it, and let the lane push the missing bullet once its current run concludes — the amendment is one line and needs no re-review. Applied to every copy: a "verified" status is a comparison against the source as it stands now, never a claim made when the file was written.

**Base the profile PRs on whichever branch actually introduces `agents/`.** When that directory is not yet on the default branch, a profile PR based on `main` carries the whole introducing diff and cannot be reviewed on its own; base it on the branch that creates the tree, fetch it via `refs/pull/<n>/head` when the branch ref is not published, and say in the body that the diff collapses once the parent lands. Use `Refs #<issue>`, not `closes` — one of N profiles does not close a fleet-wide issue.

**Decide *which* skills to version mechanically, not by reading them.** Asking "which of these sixty are
behaviour-bearing?" invites either a 60-file PR nobody reviewed or an omission. Encode the answer instead: a profile
file is in scope when it is **not byte-identical to the bundled copy**, recorded as a generated manifest (`path ·
sha256 · authored|vendored`), with the profile gate failing when an *authored* hash no longer matches the tree or when
a profile carries a skill absent from the manifest. That collapses the review to the authored diff, and it turns the
next unversioned host edit into a gate failure rather than a confession — which is the whole point of the issue: hosts
edit their own skills silently and self-report afterwards.

Two practical notes. **The issue is the channel, not the DM:** half the fleet's inboxes refuse admission
(`queue_full`), so the issue body carries the block and the DM only says "read it, then PR". And **each rule earns its
line from a measured cost** — write the cost as the reason in the issue table, because a rule with no mechanism behind
it is the first thing a future lane deletes as bureaucracy.

