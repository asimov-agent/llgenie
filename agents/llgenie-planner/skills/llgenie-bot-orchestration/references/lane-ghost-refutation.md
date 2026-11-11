# Lanes refuting ghost premises

A lane sometimes refutes a dispatch you did not send this wake — a "ghost" premise distilled from an old comment of yours, or a stale head from a prior arc. Handle it, don't fight it.

## Rules

1. **Verify the lane's cited IDs at the API, then accept the substance.** Its facts (PR merged/closed, head sha, run ids, line numbers on `main`) are usually correct even when the premise it is arguing against is gone. Read `pulls/<n>`, `pulls?state=open`, `contents/<path>?ref=main`, `check-runs/<sha>` and confirm before you repeat or reject anything.

2. **Do not re-litigate a closed premise.** Once you confirm the substance, close with a single line. No ping-pong, no resend of the DM. A lane re-stat'ing the same correction twice is a duplicate delivery, not new work.

3. **Re-correct persistent framing errors ONCE, then stop.** Two recur in this fleet and must not slip into the record:
   - `COMMENTED` reviews are NOT `REQUEST_CHANGES`. Before you let a lane call early-head reviews change-requests, read `pulls/<n>/reviews` and quote the real states.
   - An `APPROVED` authored by `asimov-agent` seconds before the merge is the **sham self-approval** folded into the #1088 evidence — never a legitimate reviewer approval. The reviewer's real record is its `COMMENTED` review. Keep the trail honest even while accepting the lane's substantive point.

4. **Transport receipts are not lane replies.** `bot_mode_dm.py` returning `status: claimed`/`queued`/`pending` is a delivery ack from the transport — absorb silently, never resend, never treat as an answer.

5. **Re-measure the lane's census claim.** "The only open PR is X" can omit a live PR the lane forgot (e.g. an active review item). Run `gh pr list --state open` yourself and correct the census once, in the same reply as the acceptance.

6. **A PR-label scan cannot see an issue-level hold.** A lane scanning `pulls/{n}/labels` (the only open PRs carry `[]`) will correctly report "no do-not-merge on the board" — and be wrong: the hold lives on an **issue** (e.g. #860: `[agent:implement, do-not-merge]`, no assignee). Issue labels never appear in `pulls/{n}`. When a lane says "no hold exists", check `issues/<n>/labels` for open `agent:implement`/`do-not-merge` issues before accepting; correct the scope once ("no hold on open PRs" ≠ "no hold on the board") without asking the lane to act on the owner-gated issue.

7. **`check-pr-closing` and `check-pr-base` are independent reds.** A PR can pass `check-pr-closing` (plain `closes #n` + squash adjacency landed) while a *different* guard step fails in the same `guard` job: `make check-pr-base` reds when a branch's merge-base with `origin/main` is not main itself (`[check-pr-base] FAILED: <sha> is NOT cut from origin/main — its merge-base is <older>`, issue #845) — the branch was cut before a later merge landed and carries another PR's base. That is a real gate red (blocks merge), a legitimate #845 rebase trigger — do NOT conflate it with #1568's clean-mergeable-under-its-own-base case, which took no rebase (#1015). Read the failing *step name* in the `guard` job log, not just the job conclusion, and note the head can drift mid-arc (re-read `pulls/<n>` head sha before concluding).

8. **Never name the phantom number in the correction — not even as contrast.** A lane stuck on "open #X" will latch onto `#X` if your corrective DM contains it at all, including "#X is closed, your work is #Y". Three DMs that said "#Y is yours; #X is not" produced three replies about #X. The fix is a dispatch containing **only the real vehicle number, once**, pointing at the on-issue claim comment (`66488...`) as the assignment source. Zero mentions of the phantom. Also record the current assignment in every follow-up (standing rule: carry the assignment, don't expect the lane to remember) and pin it on the issue thread — a DM-only assignment is lost the moment the receiver mangles it.

9. **A lane quoting specific machinery you never wrote is board infidelity — certify absent, then file it.** "Your amend worked", "guard = fail job 126996060863", "check-pr-closing now CLEAR" — when none of those words exist in any comment on the PR by any actor, the lane is reading a synthesised/stale board row, not your text. Prove absence probatively in one measurement: `issues/<n>/timeline` has no `edited` event (committed→merged→closed only), `issues/<n>/comments` + `pulls/<n>/comments` contain zero matches for the quoted phrases, and `pulls/<n>` shows `merged_at == closed_at`. Then say "stand down — the object is not in the API", re-route to the lane's real vehicle, and **file the read-path defect once** (which channel surfaces merged/closed PRs as open reconcile work) so the next wake is an auditor's job, not a repeat of your certification. Two lanes conjuring phantoms in one hour is a pattern, not two coincidences.
