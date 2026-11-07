# Live→tree profile fold (folding a lane's live profile into `agents/`)

A "fold" copies a lane's LIVE profile files (`~/.hermes/profiles/<profile>/…`) into the tree
(`agents/<profile>/…`) byte-identically, so the live rulebook stops being the only copy. The live
profile is written continuously by the owning lane, which is what makes this different from any
other sync: **your snapshot is a moment, and the file grows after you take it.**

## The loop (repeat until a run of the gate is clean at the PUSHED head)

1. Fetch current `main`, cut a fresh worktree, and record the base sha in your claim comment.
2. Run the live-direction gate for your lane (see *Running the comparison for real* below) — the
   gate is the authoritative SCOPE, not the dispatch's file list, which is usually an example.
   A dispatch naming three files routinely under-counts; fold every file the gate names.
3. Copy each named live file into the tree verbatim, then prove byte identity with
   `scripts/verify_fold_identity.py` (raw bytes, so a trailing newline cannot fake a match).
   Poll the live set twice a few seconds apart first and confirm the same hashes: the owning lane
   writes continuously, so if a file's hash moved between the two samples you are racing it and the
   fold will be stale by the time you push. Compare like-shaped values (a tuple against a string,
   or a sha256 digest of one side against the raw BYTES of the other, makes every file look
   changed/mismatched — that false alarm has cost a full re-poll). Never hand-roll the identity
   check: use `scripts/verify_fold_identity.py` or `cmp -s`. A digest-vs-bytes comparison always
   reports a false mismatch and sends you re-folding a file that was already byte-identical.
4. Re-run the gate: the lane's live-direction findings must be ZERO. Other lanes' findings are
   ambient drift — leave them, and say so in the PR body.
5. Commit ONCE (one fold commit for the whole recreation), run the docs/lint gates at the head.
6. **Re-run the live-direction gate immediately before pushing, and again at the pushed head.**
   If the live lane wrote anything in between (a file grew, or a brand-new file appeared under the
   profile), fold it into the SAME commit (`git commit --amend`), re-push with a pinned lease, and
   re-verify. A brand-new live file is normal, not exceptional: the owning lane adds references
   while it works, and only the gate's `absent-from-tree` class catches them.
7. Verify at the remote ref, not your worktree: `git clone -q --branch <branch> --single-branch
   <url> /tmp/verify && cd /tmp/verify && <gate>` — the reviewer and CI see the pushed tree, and a
   local worktree can hold uncommitted edits that make a gate look green.

Backing out of step 6 is never "open a second PR": amend the one fold commit and `git push
--force-with-lease=<branch>:<sha>` after fetching the branch tip in the same breath (it is your own
unmerged branch, so the rewrite is safe; a lease pinned to a sha you fetched earlier is not).

## Running the comparison for real (a green can be vacuous)

`check_agent_profiles.py` resolves the live profiles root from `$HOME`. In a container whose `$HOME`
is not the operator's, the live comparison is **SKIPPED** and the run passes while comparing
nothing — an exit 0 that proves only that the tree matches itself. Make it run by mounting the live
dir where the container's `$HOME` will look for it:

```bash
docker run --rm -u root -e HOME=/root -e PYTHONPYCACHEPREFIX=/tmp \
  -v "$PWD":/repo -w /repo \
  -v "$HOME/.hermes/profiles":/root/.hermes/profiles:ro \
  llgenie/test:latest \
  sh -c 'python3 scripts/check_agent_profiles.py --only live-longer,absent-from-tree 2>&1 | grep <lane>'
```

- Mount at the path `$HOME/.hermes/profiles` resolves to INSIDE the container, not at an arbitrary
  `/live` — a mount in the wrong place silently yields SKIPPED again, which looks like zero findings.
- Read a few raw lines (`grep <lane>`) rather than only `wc -l`: a zero from a skipped comparison and
  a zero from a clean comparison print the same number.
- `-e PYTHONPYCACHEPREFIX=/tmp` keeps root-owned `__pycache__` out of the worktree, which otherwise
  blocks `git worktree remove` later.
- `--only <live-longer>,<absent-from-tree>[,<live-lines-missing>[,<live-edited-not-tree>]]` scopes
  the run to your lane's classes; without the filter the same command prints every other lane's
  drift and reads as failure. The gate has FOUR live classes — `live-longer`, `absent-from-tree`,
  `live-lines-missing` and `live-edited-not-tree` — and a scoped run that omits one can print zero
  for your lane while the full run flags it.
- **Run BOTH forms and make the same-lane counts agree before claiming clean.** The scoped run is
  the acceptance metric reviewers quote, but it can print zero for your lane while a FULL no-args
  `check` still lists same-lane rows in a class the filter did not surface — a zero taken from the
  scoped form alone has been wrong, and it hid two genuinely-unfolded refs. Declare done only when
  the scoped same-lane row count AND the full no-args same-lane row count are both zero; when they
disagree, the full run is right — fold what it names.

## Editing a PROTECTED agent-instruction file (`agents/<lane>/SOUL.md`)

A write to a lane's `SOUL.md` — the versioned home for its standing behaviour — trips the
agent-instruction guard and is held pending explicit approval. The guard can come back as a HARD
tool refusal, not only a silent approval timeout: `BLOCKED: write to protected agent-instruction
file(s) … Do NOT retry it or attempt the same edit via another path (terminal, execute_code, etc.).
Silence is not consent.` In a headless / no-tty run silence is refusal, so every OTHER edit in the
branch lands while the SOUL file is silently left untouched. The fold then looks done but the core
deliverable is missing.

**Do NOT bypass the refusal.** Once the guard says "do not retry or route via another path", the
write is off the table for this turn — do not re-issue the same `patch`, do not `cat >`/
`git apply`/Python-write the same bytes through `terminal` or `execute_code`. A protected-write block
is about the FILE, not the tool that touched it; beating it through a subprocess is the
defect the guard exists to stop, and it does not produce a PR you can honestly defend. This holds
even when the file is your OWN lane's `agents/<lane>/SOUL.md` and the dispatch names it as the
vehicle (that is legitimately yours to write *with consent*, not to force past the block).

When a dispatch's deliverable IS committing standing behaviour under `agents/<lane>/SOUL.md` (yours
or one the issue names — not a push into another lane's PR):

- Ask the owner directly with `clarify` BEFORE or as soon as the write blocks: name the file, quote
  the exact rule text being committed, and say why it must live in the tree rather than the private
  live profile. A `clarify` can itself time out — if BOTH the write prompt and the `clarify` go
  unanswered, that is refusal, not permission; stop asking and take the parked state below.
- Apply the write only after consent, then re-run the branch's full gate set — the SOUL surface is a
  `check-docs` NOTE_SURFACE, so that change owes the change→note→fragment trio.
- **Parked state when blocked with no consent — the correct terminal state.** Author every
  NON-protected deliverable in the worktree (the `openspec/changes/<name>/` dir — `agents/**` is not
  docs-only, so the #1807 presence gate needs its own change dir — plus the change-note + agent-wiki
  fragments, `make changes-index`), so the branch is one edit from done the instant consent lands.
  But commit and push NOTHING: leave the authored files untracked/uncommitted, keep `HEAD` at the
  base sha, and do NOT open a hollow PR — a PR whose diff omits the very SOUL rule it claims would
  merge nothing and is worse than no PR. Report the measured state (worktree path, branch, base sha,
  `git log --oneline -1` still the base tip, `git diff --stat HEAD -- agents/` = 0) and name the
  owner-consent-for-`<file>` as the single remaining dependency.
- Never substitute a private live-profile edit for the tree edit: `make sync-agent-profile` mirrors
  tree→live, and a private edit is exactly the drift the versioned home exists to prevent. Never drop
  the piece silently either — report it as the one blocked deliverable if consent is refused.
- Scope discipline still applies: a doc-only, workflow/gate, engine/serving, or structural-design
  change belongs to that lane. This rule covers the case where the DISPATCH names the SOUL file as
  the vehicle, not a licence to edit a neighbour's lane unasked.

## Acceptance is your lane's row count, not the gate's exit code

- **A whole-gate `rc=1` with zero SAME-LANE rows is PASS.** The no-args `check` aggregates every
  lane's ambient live drift; CI skips the live comparison, so other lanes' rows are expected host-
  side and are not yours to fold. The acceptance metric is your lane's row count across all four
  classes == 0, never the process exit code. Report the row count and say the residual rows are
  other lanes' — do not chase `rc=0`, and do not "clean up" a neighbour's drift.
- **Do not fold your OWN lane's drift.** Your own profile's `SOUL.md` and skills legitimately show
  up as live-longer / absent-from-tree under your own lane; folding them here is out of scope and
  forbidden — a SOUL/skill change to your own profile needs its own issue+PR (#851). Leave them,
  state in the PR body and the lane report that they are own-lane ambient drift the fold did not
  touch, and let the owning dispatch handle them.
- **Tree-bytes > live-bytes is not a failure class.** A tree copy that is one blank line LARGER
  than live is the lint-normalisation case (see below), not `live-lines-missing`; do not "fix" it
  by folding the shorter live bytes back over the tree. The live file converging (tree→live) is the
  owning lane's job.
- **A DIRECT single-file skill EDIT is not a fold, and does not owe the target lane's whole drift.**
  When your issue scopes you to "edit one skill file" (its text says "no surface beyond the skill
  file") but `make sync-agent-profile PROFILE=<target> CHECK=1` ALSO reds on OTHER pre-existing
  files in that same target lane, do NOT fold them: prove YOUR edited file is byte-identical on
  both sides (`cmp` / same hash tree vs live), then report the residual drift as a measured
  BLOCKER — name each file, its tree-vs-live byte count and the direction (tree truncated ⇒ a
  sync would DELETE live lines), and say the whole-lane `CHECK=1 exit 0` clears only after that
  lane folds its own drift via its own issue+PR. Put the same in the PR body so a reviewer sees
  the one acceptance line that cannot go green here is not this vehicle's defect. Folding another
  file of the target lane drags that lane's scope into your vehicle and is forbidden.
- **An issue that names a section (e.g. `## Lane rules`) the live/tree file no longer has means the
  file was RESTRUCTURED since the issue was filed — locate the current equivalent home** (grep the
  tree file for the rule's wording), patch there, and note in the PR body that the cited section
  name is pre-restructure. Never invent the named section to satisfy the issue text.

## Verbatim fold vs. the tree's lint gate

Folding live bytes verbatim can red `make lint` on content the live file itself carries (a heading
immediately after a code-fence close is the common one). Decide it, do not improvise it:

- Prove you introduced it: run the lint gate on the BASE tree. Green base + red head = the folded
  bytes did it.
- The minimal tree-side fix is the one blank line. A tree-only blank INSERTION loses no live line,
  so the live-direction gate (`live-lines-missing`) stays at zero — confirm that, rather than
  assuming it.
- Document it in the PR body as the fold's SOLE deviation (`+1 blank line, no live line changed`),
  and tell the owning lane its live file carries a lint violation to fix at the source. Silently
  normalising the live copy defeats the byte-identity check; normalising the tree copy without
  saying so looks like a sloppy fold.

## Naming the vehicle

The fold's note/fragment filenames must reference the TRACKER issue, never a PR or issue number
that happened to be nearby in the session — a `…-repost-<unrelated-number>.md` slug is a filename a
future reader cannot resolve. Rename before committing and re-point the changes-index fragment link
at the new name.

## Each amend makes the PR body's numbers stale

The PR body records a head sha, a file count, and per-file byte tallies. Every `--amend` +
`--force-with-lease` re-push silently falsifies all three, and prose is not re-read by anyone:

- After the final amend, sweep the body for the OLD head and the OLD count and rewrite them
  (`grep` the body file for the previous sha before you post it). A body saying `7 files` and
  `head <old>` while the branch carries 10 is a review-blocking inaccuracy, not cosmetics.
- Read the body BACK after `gh pr edit --body-file` and assert it carries the new head sha, still
  carries `closes #<tracker>`, and no longer mentions the superseded sha. A successful edit exit
  code is not the fact; fetch `gh pr view --json body` and check the strings.
- Parse that read-back as JSON (`--json body` into a structured parse) rather than jq string
  interpolation — an interpolated `.body` query has come back empty and made a landed edit look
  like it failed. Capture the issue number in the closing-keyword pattern
  (`(?i)clos\w* #(\d+)`); a pattern without a capture group returns `['clos']` and makes an
  already-correct body look unverified — fix the pattern once, do not re-query the API repeatedly
  hoping a different shape appears.
- Post one head-advance comment per force-push naming old→new sha and what changed; the body is the
  current state, the comment is the history a reviewer can follow.

## When a peer lane reports your head as stale (or repeats a refuted claim)

A reviewing lane (planner, reviewer) can dispatch a head sha that is older than what you actually
pushed — it measured before your force-push landed, or from a stale short-ref. Do not re-push, re-
fold, or argue from memory. Decide it with measurement:

- **Re-measure from two independent sources in the same breath** before replying:
  `gh pr view <n> --json headRefOid` (or `gh api repos/<o>/<r>/git/ref/heads/<branch> --jq .object.sha`)
  AND `git ls-remote <url> refs/heads/<branch>`. If both agree with your pushed head, the peer's sha is
  simply stale — reply citing the two measured shas and stop. Two sources agreeing is the fact; one
  exit code or one API field is not.
- **Before you report a head to a peer, re-read the remote ref and quote THAT sha.** A report
  assembled from a plan or an earlier measurement goes stale under a force-push, and reporting a
  superseded head is what triggers a false "the head moved under us" refusal.
- **A verbatim redelivery is not a new instruction.** When a peer repeats a claim you have already
  measured and refuted, hold: do not re-fold, do not resend the same confirmation. One measured
  refutation with the two shas is the whole answer; a second and third identical re-send reads as a
  loop and teaches the peer to distrust the channel.
- **Never suppress a genuine move.** If the two sources DISAGREE with your worktree, the branch really
  moved — fetch and re-verify before anything else. The rule protects against a stale claim, not
  against a real advance.

## A clean gate result is time-stamped, not a property of the branch

The trap that outlasted every stale-sha argument: your head did NOT move, yet the FULL no-args gate
at that SAME tip went from 0 same-lane rows to 4. Nothing was wrong with the branch — the owning
lane's live files kept growing after your fold commit (`acceptance-at-moving-head.md`
5338→8025 b, `agent-profile-sync.md` 11646→13523 b, mtimes AFTER the fold), so each file now reads
`live-longer` AND `live-edited-not-tree`. The gate compares the pushed tree against the CURRENT live
profile, which changes under you — so "acceptance met at head X" is only true as of the second you
measured it. When you re-gate a tip, **re-measure the live set in the same breath**; a headMatch is
not a gateMatch.

- A refusal you cannot refute is not a restatement to argue — re-run the gate yourself at the exact
  tip the peer names, quote the sha AND the full no-args output, and if it reads N>0, concede and
  hold. Conceding a correct measurement is cheap; re-folding a moving target is churn that gets
  overtaken in under a minute.
- **The loop closes on a frozen live set, not on a re-push.** Do not amend again until two polls a
  few seconds apart show the same hashes for every flagged ref; a re-cut taken while the writer is
  still active is stale before CI reads it.
- **A peer can misattribute a claim to you.** A reviewing lane may quote "you said X" where X was
  never in your reply (a different head sha, a rebuttal you never posted). Before defending or
  conceding, check the actual artifact — `gh api .../pulls/N/commits` for the real oid list and
  `gh api .../issues/N/comments` for what you truly posted. Correct the record ONCE with the measured
  artifact, then hold; correcting the same misattribution twice feeds the loop the rule above warns
  against.

## Proving a committed fold, and monitors that only see file-tool writes

The commit is the artifact, not your working tree and not a tracker's telemetry. Prove the change
with git against the base sha:

- `git cat-file -e <base>:<path>` — exit non-zero proves the file was ABSENT on the base (the
  absent-from-tree class really is added by this commit).
- `git show HEAD:<path>` piped to a sha256 and compared against the raw bytes of the live file —
  byte-identity proved from the committed blob, not a re-read of the worktree.
- `git diff --stat <base>..HEAD` — the whole change in one line (files/insertions/deletions).

A fold is written through `shutil`/`git add`/`git commit` — a subprocess, not a direct file-tool
write. Some integrity monitors that track only direct `patch`/`write_file` writes therefore cannot
observe it and can report **"no task-relevant changed path"** on a fully committed, pushed and
gated change. That report is a false negative about the monitor, not evidence the work is un-done.
Do NOT fabricate a file edit to turn such a monitor green — that falsifies a clean fold to satisfy
telemetry. Quote the committed bytes (`cat-file -e` base-absent, committed==live sha256, diffstat)
and hold. Two corollaries, because the same report echoes on every turn:

- **When the identical report repeats, one measured refutation is the answer.** Do not re-run the same
  verification a third and fourth time hoping it changes — a loop of identical measurements proves
  nothing new and delays the real work; state the two shas and stop.
- **Do not rewrite byte-identical content through the tracked tool to register a `write_file`.**
  A no-op edit (same bytes, different channel) exists only to flip the monitor and is the same
  falsification by another route; if a genuine task-relevant edit remains, make it, otherwise hold.

## An `absent-from-tree` live-only reference rides its own single-file commit vehicle

When the live-direction gate names a reference that is `absent-from-tree` (the owning lane created a
brand-new reference only in the live profile), the fix is a **single-file commit with its own tracker
issue and its own PR** — one file, one commit, one vehicle. Do not bury it inside a multi-file fold
PR: it has its own scope, and a reviewer cannot tell a brand-new reference apart from a re-folded one
when both ride one commit.

- Copy live→tree byte-identically, prove it with `cmp -s` / `scripts/verify_fold_identity.py`, and the
  PR body carries `closes #<the-single-file-tracker>` plus the `AGENTS: <base-sha>` line — NEVER a
  closing keyword for the parent fold issue, whose acceptance is met only by the fold itself (see
  `check-pr-closing` below: the closing set must match the squash set exactly).
- The single-file commit UNBLOCKS the parent fold's acceptance but does not satisfy it: the fold stays
  pending until every `absent-from-tree` reference has its file in the tree. Sequence them; do not
  re-fold a half-populated set, re-open the fold, or force any vehicle through.
- A vehicle you do not own — a reference routed to another lane (a docs-lane file, an engine file) —
  is that lane's to deliver. State the dependency ("fold blocked on <their file> in-tree") and hold;
  opening a parallel branch on another lane's file is the push-you-were-not-dispatched-for defect.
- **An ORDERED multi-step fold whose re-cut is gated on the prerequisite vehicles MERGING is PARKED,
  not pre-cut.** When a coordinator orders "do not push the fold re-cut until the single-file
  commits have MERGED to main," obey the ordering: branching the fold off the current main tip
  before the prerequisites are in-tree re-emits the exact `absent-from-tree` rows the fold is meant
  to clear, so the only correct terminal state is a hold. A hold measured against an external
  owner-side merge is complete work, not a shortfall — never merge/arm to unblock it yourself.
  Report the two prerequisite PRs' measured `state`/`headRefOid` and the live main tip, and re-cut
  on the pass where both read MERGED.
- **Cut the re-cut from the sha you FETCH AT THAT MOMENT, never from the base the dispatch quotes.**
  A dispatch names a fold base like `506a9fb4` or `6f7a2d31`, but those are filing-time snapshots:
  by the time you act, main has usually advanced past them (the cited sha is already an ancestor),
  and a branch cut from an ancestor either re-emits absent rows or conflicts. `git ls-remote
  https://github.com/<o>/<r>.git refs/heads/main` the instant you cut, and branch from that tip.
- **The issue's quoted LIVE blob hash is a filing-time snapshot too — fold the CURRENT live bytes,
  not that hash.** An acceptance criterion that says "fold source is live `<ccba9977>`" was true
  when the issue was filed; the owning lane has written since, so hashing the live file now yields a
  different blob (`<6086452f>`). Hash the live file at the moment you copy (`git hash-object
  <live-file>` or `sha256sum`) and fold THOSE bytes; committed==live-NOW is the acceptance, and the
  issue's older hash is not a target. Do not re-fold toward the stale hash or block on it. State the
  deviation in the PR body (the current live sha and "tree==current live is byte-identical") so a
  reviewer diffing against the issue's stale hash is not misled, and confirm it is a new live-drift
  fold, not a revival of an earlier already-merged fold of the same file.
- **A live file larger than the profile tooling's size cap CANNOT be folded byte-identically — that
  is a slim decision, not a mechanical fold; do not claim it.** A live reference over ~100k chars
  exceeds the max file size the skill/profile tooling accepts, so a verbatim copy is refused by the
  size gate before it can commit. The only fold that fits is a slimmed one, and shrinking live
  content loses behaviour (the same lost-line caution as a tree→live sync) — its premise is a
  SEPARATE slim issue, not this mechanical vehicle. Measure the live byte size, flag it to the
  planner and the lane that owns the file ("fold blocked: live is N>cap bytes, needs a #1135-class
  slim first"), and hold — do not fold the truncated side and do not claim the vehicle.

## `check-pr-closing` needs a body whose closing set MATCHES the squash set

PR CI runs `make check-pr-closing`, which compares the closing set in the joined commit messages to
the closing set in the PR body and requires the two sets identical. The closing set is ONLY an
ADJACENT `closes|fixes|resolves #<n>` (keyword + whitespace + `#`, as the regex `CLOSING` in
`scripts/check_pr_closing.py` reads it); a bare `#<m>` sentence in the body is NOT in that set and
does NOT red the mismatch, so a superseded issue number merely mentioned in prose is harmless for
it. Two OTHER halves are what actually red: (a) an `Issue: #<m>` line, or a title/commit-subject
ending `(#<m>)`, is a CLAIM that must be adjacently closed in BOTH the squash text and the body;
(b) an `agent/*` head whose body names any `#<n>` but carries NO adjacent closing keyword at all.
Read `scripts/check_pr_closing.py` (`report`/`check`, or run `check --body-file … --base <base>
--head <branch>`) to see the live rule before trimming a body — the gate's real behaviour beats a
remembered summary of it. Prove rc=0 locally via
`make check-pr-closing PR_BODY=<fixed> PR_BASE=<base> PR_BRANCH=<branch>` (the command CI runs), then
push.

**A body-only `gh pr edit` does NOT re-trigger the gate.** CI reads `PR_BODY: ${{ github.event.pull_request.body }}`
from the EVENT payload, and `gh run rerun` replays that stored payload verbatim — so an edited body and
a rerun STILL evaluate the old body. The new body reaches the check only through a NEW pull_request
event: amend the same tree (`git commit --amend --no-edit`, one commit kept) and `--force-with-lease`
the branch so the synchronize event carries the current body. Verify via `statusCheckRollup` that a
fresh `guard` run started AFTER the push reads SUCCESS.

Do not chase a `holds` gate that reds with `cannot read the head of run <id>: gh: Not Found` — that is
a pipeline infra 404 (a run id the gate cannot resolve), the ci-pipelines lane's artifact, not a
fold/body defect; report it to that lane and hold.
