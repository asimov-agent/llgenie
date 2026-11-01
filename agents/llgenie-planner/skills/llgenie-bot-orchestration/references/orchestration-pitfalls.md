## Pitfalls

- **Four gates on this board print the same output for "found nothing" and "could not tell."** #1086 compared one
  direction only; #1108 printed `OK` for profiles that declare zero rules; #1123 enforced note→fragment but never
  change→note; **#1134 aborted with a `UnicodeDecodeError` and printed no FAIL at all, so every caller read a
  crashed check as clean.** That last one hid, for hours, a **125 KB skill directory existing only on one host**.
  **A check that cannot say "I did not run" is not a check** — whenever you read a green from a gate, ask what its
  "could not tell" path prints, and if the answer is "the same thing", the green is not evidence.
- **Before asserting any check gates a merge, read the ruleset.** A repository whose `main` ruleset is only
  `deletion, non_fast_forward` has **no required status checks**, so no cancelled or red suite blocks anything — the
  review is the only gate, and a green-except-matrix board is *information, not protection*. The armed-vs-gated
  question (should a PR wait on a leg that cannot block?) is answered with the ruleset, never with the check list:
  `gh api repos/<o>/<r>/rulesets/24862727 --jq '[.rules[].type]'`. Measured asimov-agent/llgenie: five legs dead at
  the same 60m ceiling, all cancelled, none of them load-bearing against a merge.
- **A cancelled leg is two opposite events; only the duration separates them.** `cancelled` at ~18 s is a supersede
  (a newer push superseded the run); `cancelled` at the `timeout-minutes` ceiling — ~60m2x on five independent
  branches and start times — is the declared timeout doing its job, and a constant that tight is a ceiling, not a
  coincidence. Report the **attempt number and the duration** beside every `cancelled` reading; the conclusion alone
  is meaningless.
- **When a lane regresses to the same wrong numbers despite two corrections, stop re-correcting and post the
  authoritative state on the PR** where every future reader — bot or human — hits it before acting. The repair that
  works is the one that replaces the unreliable prose as the record, not a third DM. Then say once, plainly, that the
  ground rule is `paste the command output, not a sentence about it`, and refuse to be the correction loop a fourth
  time.
- **Check your own work the way this fleet checks others.** `references/proving-bot-claims.md` now carries the
  instruments that caught the most errors tonight, each written as a rule: `created_at` is not a start time; the
  positive value of an eventually-consistent field is proof and the negative is not; a compound shell command is
  classified by its first matching segment, so a test chained onto an edit is invisible; a versioning PR is a
  checkpoint rather than a state; and a sentence that says `closes #n` is not a link. Read that file before
  reporting a verdict, not after being corrected.

- **A skill file that hits the ~100,000-character cap becomes un-patchable, silently.** `skill_manage` refuses the
  save and rolls back every touched skill, so the lesson you believe you recorded lands nowhere - or lands only in
  the duplicate profile copy, which is how a lane "keeps forgetting" a rule it keeps writing down. `wc -c` the file
  before blaming the lane; the remedy is a reference file plus a pointer, never an edit to the cap. Recipe (size the
  sections, move one verbatim, prove `missing: 0`, re-lint, prove with a real save) and the extraction-not-worktree
  check for another lane's scripts: `references/agent-profile-sync.md`.

- **A claim with no branch is theatre.** The 3h TTL blocks every other implementer from the issue that may be
  reddening all PRs. Release it in a comment with the 404 as evidence, then re-dispatch.
- **Never enumerate claims with `gh issue list --search`.** The search returns a subset, so a live claim is
  invisible and the pass dispatches a second implementer onto work that is already in flight. Read *every* open
  issue's comments and regex the marker, then compare it to the branch list:
  `gh issue list --state open --limit 200 --json number,comments --jq '.[]|.number as $n|.comments[]|select(.body|test("bot-claim:"))|"\($n) \(.createdAt) \(.body)"'`.
  A claim whose `run=<id>` already reports verdict `implement` + `PR: #<n>` is live work, not a dispatch target.
- **A finished `refine` run leaves a live-looking claim.** `run=<id>` completed `success`, verdict `refine`, no
  branch, TTL still counting: the issue is unowned. Release and hand it to the specialist for its class — the CI
  bot will not pick it up again inside the TTL.
- **Never run a prune to "tidy up" before a dispatch.** The worktree you would delete is often the in-flight work; the
  destructive target is owner-only (#794) and a bot following `AGENTS.md:483` literally destroys its own run.
- **Deleting a branch whose issue is open throws away the only work product.** Check
  `compare/main...<branch>` first: 1 commit and a few behind is salvageable (hand it over to finish the PR); far
  behind across generated files is a rebuild, so delete and re-implement fresh.
- **An issue with an open PR is not dispatchable work.** Before handing an issue to an implementer, check
  `gh pr list --state open` for a PR whose body closes it; a second branch for the same issue is a duplicate artifact,
  and the correct instruction is "do not implement this, it is in review".
- **An automated approval is not the owner's approval.** A PR can show `reviewDecision: APPROVED` and be merged by the
  same non-human identity seconds later — read `gh api .../pulls/<n>/reviews` (`submitted_at`, `user.login`) against
  `mergedAt`/`mergedBy`. When approve and merge come from one identity inside a few seconds, report it to the owner as
  an incident; never present it as "your approval was given".
- **Labelling everything `agent:implement` floods a 3/day bot** and builds a queue nothing drains — especially while
  its implement leg is broken. Order the queue, label the head of it.
- **A `success` run can be a decision with no artifact.** A CI triage leg that returns `refine` posts a restated spec,
  labels the issue refined, opens no branch and still exits green. Treat that issue as unowned and hand it to the host
  implementer; never read `success` as “being worked”. Check the verdict comment and the branch list, not the run's
  colour.
- **Two lanes converging on one gap is a sign the gap is real — and still one issue too many.** When a second issue appears minutes after yours describing the same defect, close the duplicate rather than merging the prose, but **read it first**: the newer filing often carries a criterion the survivor lacks (a failure mode, a second direction of the same check, a negative control). Fold that into the survivor as a supplement comment, name which issue keeps the trail and which acceptance criteria came from the closed one, and say plainly that two lanes reaching the same measurement is evidence for the gap rather than a mistake by either.
- **Append to a workspace file, do not keep the fleet state in your head.** Write the run/claim/branch snapshot to a
  JSON file and diff it on the next pass: a bot that was quiet last pass and is still quiet is a finding.
