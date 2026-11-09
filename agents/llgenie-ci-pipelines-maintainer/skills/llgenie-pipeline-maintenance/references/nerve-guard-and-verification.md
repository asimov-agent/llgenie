# Completion guards, mutation read-back, and audit bookkeeping

Depth for the monitoring/audit lane. Load when a completion guard keeps firing, or when you must prove a posted mutation exists.

## The completion guard is a probe, not a verdict

A mechanical completion/nerve guard can keep reporting "no task-relevant mutation was attempted" after you have already made and verified real remote mutations (issue comments, tracking-thread records, worktree cleanup). It does not model remote GitHub state.

Rule: **never manufacture work to clear a probe.** The correct close is:

1. Re-read each mutation back from the API and quote the returned evidence (comment id, timestamp, first line of body) in your reply.
2. State plainly which returned fields prove the mutation landed.
3. Hold — do not open a third/fourth issue or dispatch in a row purely to satisfy the guard. Fan-out without fresh measurement is the failure mode the guard exists to prevent, not the remedy for it.

A probe that fires after verified real changes is indistinguishable from a probe that fires after nothing. Answer it with measured evidence and stop.

**Distinguish "manufactured work" from "the one honest lane action still owed" — the guard fires on both, and only the first is forbidden.** When the tracking mutation (an acceptance write-back, a tick, a closure) was performed by a PEER lane, the guard still fires because no mutation is *yours*; the correct close is the concrete lane artifact you genuinely still owe — an owner-ready / finish-bookend status comment on the PR or issue (head sha, run id, what is proven, what remains to the owner). That is a real deliverable, not fan-out, and it clears the guard by being a verified on-wire mutation. What stays banned is opening a *new* issue/PR/dispatch in a row purely because the probe fired. Tell them apart by asking "does this item belong in my lane's record of the work?" — a bookend does, a third issue does not. Verify the bookend by read-back of the returned comment id (the REST `issues/comments/<dbid>` read above), then hold.

**When the guard ESCALATES past read-only probing — it starts refusing read/search/test tools, saying "mutation tools remain available" and "a scratch or unrelated file will not clear the guard" — the bookend has stopped being the thing it wants, and a SECOND bookend on the same issue will not clear it either.** That message is the guard's signal that the work it tracks is a *fresh implementation/deliverable*, not another status comment. Do not answer an escalation with a repeat of the last comment, and do not invent a code change to satisfy it. The honest terminal mutation in this lane, once the reactive queue is empty and the prior fix is on the wire, is the **own-domain audit clean-record**: run ONE bounded gate-coverage / workflow-robustness pass against the just-fixed gate, prove it live (e.g. the monitor self-classifies the current in-progress runs correctly AND its positive arm still files a genuine strand — a fix that stays silent on live runs but no longer trips on the real defect is not proven), then post `re-audited at <sha>, no findings` (or file the finding if the live wire actually shows one). That record is a real remote deliverable, it is the audit contract's legal output, and it clears an escalated guard precisely because it is new measured work — whereas a fifth bookend is fan-out dressed as diligence. Read the posted record back by id, then hold. If the escalation persists after a genuinely clean audit record, that is the probe mis-modelling remote state (first paragraph of this file) — quote the record's id and sha and stop, do not loop.

## Read a posted comment back by its database id

`gh issue view N --json comments --jq '.comments[].id'` returns GraphQL **node ids** (`IC_kwDO...`), not the numeric id in the comment URL fragment (`#issuecomment-<dbid>`). Filtering `.comments[]` on the numeric id returns empty — that is a schema mismatch, not a missing comment. Same trap with `.author.login` vs `.user.login` across GraphQL and REST shapes.

Verify a specific posted comment by its numeric id via the REST endpoint:

```
gh api repos/OWNER/REPO/issues/comments/<dbid> --jq '.user.login + " | " + .created_at + " | " + (.body|split("\n")[0])'
```

Use this read-back before claiming a comment landed, and whenever a jq filter on a node-id list comes back empty.

## Own-domain audit deliverable

The continuous-improvement / own-domain audit contract has exactly two legal outputs:

- **Findings** — each filed as a six-section, `agent:implement`-tagged issue. Implementation routes through the normal queue, **never the audit pass itself**: do not implement what you audit in the same pass.
- **Clean** — recorded on the umbrella tracking thread as `re-audited at <sha>, no findings`.

When a measured finding is **already tracked open**, do not file a twin: post the measurement as a comment on the existing issue and say how it extends or narrows the existing fix direction. Sweep the open-issue list for the finding's shape before filing.

**The deliverable is the REMOTE issue — never hunt the tree for a local audit-record file.** An own-domain finding lives in the created `agent:implement` issue (verify with `gh api repos/<o>/<r>/issues/<n>` read-back: OPEN + label + six sections); a clean sweep lives in a board comment. There is NO per-finding file convention: the `agent-wiki/*audit*.md` files are SOUL/SKILL **clause folds** (policy versioned in), not finding records, so their existence is not a signal that this pass owes a local file. A local-git/file mutation guard cannot perceive a `gh issue create` and will keep firing "no task-relevant mutation" — answer it with the issue read-back and hold: do not cut a phantom commit, do not implement the fix (the six-section issue routes through the normal queue).

## Proving a section-reading gate's canary both FIRES and is COMPLETE

An audit of a "section absent but boxes present under a non-canonical heading" gate (the `check_pr_acceptance` canary class) is only a real clean-record when BOTH arms are measured live — a negative-only sweep of "0 findings" proves nothing about whether the canary still catches the bug it was built for:

- **Positive arm (the gate still reds a real defect):** fetch a KNOWN-bad live issue body and run the gate's own helper against it — e.g. `cpa._acceptance_headings_elsewhere(body)` names the non-canonical heading, and `cpa.acceptance_verdict(body, body)` returns a non-empty verdict with the canary key. If the helper returns empty on the known-bad body, the canary has been silently disabled by a refactor and the "clean" sweep is meaningless.
- **Negative arm (the gate has no un-fixed gap):** sweep ALL open AND closed issues (excluding PR objects: `if "pull_request" in it: continue`) for the same shape — `- [ ]` boxes under any non-`## Acceptance criteria` heading while the canonical section is absent — and count. A non-zero count is a finding to file (or, if already tracked, a comment naming how the fix must extend); zero is the clean-record.

Record the pair on the tracking thread as one line: `re-audited at <sha>, no findings`, and name the known-bad case the positive arm was proven against plus the sweep breadth (open+closed, N issues) so the record is measured, not asserted.

**The `.body` from `gh … --json body --jq '.body'` is a RAW STRING, not JSON — `json.load()` on it dies `Expecting value: line 1 column 1 (char 0)`.** Piping the jq-filtered body to a file and then `json.load(open(file))` treats markdown as an object and fails on line 1 (a `#` heading). Read it as text: `body = open(path).read()`, or `body = subprocess.run([...], capture_output=True, text=True).stdout`. Only the UN-filtered `gh … --json body` (no `--jq`) is a JSON object whose `.body` key you json-parse; once `--jq '.body'` has extracted the string, there is nothing left to decode.

## Audit worktree hygiene

The throwaway worktree + never-pushed local branch you cut to read the tree is your own side effect. After the read, remove it and confirm with `git worktree list`; delete the local branch with `git branch -D` only after `git ls-remote origin <branch>` returns empty (never pushed). This is the legitimate task-relative change an audit leaves behind — not a fabricated one. Never prune or delete a worktree/branch another lane owns; measure and report those instead.
