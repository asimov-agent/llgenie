# PR body hygiene: a body is prose, not a serialized request

A lane can open a PR whose **body** is the raw `gh pr create` request payload instead of the
markdown it holds: `{"title": "...", "head": "...", "base": "main", "body": "## What & why..."}`.
The review surface then shows the owner raw JSON, and the repo's `check_pr_hygiene.py` `pr-body`
check passes it green because the check only rejects **empty/placeholder** bodies — a JSON object is
neither, so the defect is silent. The same payload can arrive as a **comment** (a create-comment
request dumped into the thread); apply the same object-vs-prose rule to both.

## Detect before you accept a PR into the board

```bash
gh api repos/<owner>/<repo>/pulls/<n> --jq '.body' > /tmp/body.json
python3 -c 'import json; json.load(open("/tmp/body.json"))' 2>/dev/null \
  && echo 'SERIALIZED OBJECT — unwrap it' || echo 'prose, clean'
```

A body that starts `{`, parses as a `dict`, or carries the create-request keys (`title` + `base` +
`body`, often `head`) is the serialized payload. Check for those keys, not just `isinstance(dict)`:
a body that legitimately embeds a JSON code block should not be flagged.

## Fix: unwrap the inner markdown and PATCH the body

```bash
python3 -c 'import json; print(json.load(open("/tmp/body.json"))["body"])' > /tmp/body.md
gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@/tmp/body.md
# read back: .body must no longer parse as a dict, and must still end with the adjacent
# `closes #<issue>` line the closing gate requires
gh api repos/<owner>/<repo>/pulls/<n> --jq '.body' | tail -3
```

After the PATCH, re-verify nothing regressed on the closing gate: the unwrapped body must still
carry a plain adjacent `closes #<issue>` (proximity rules in `pr-closing-gate.md`).

## The six-section `issue_body` validator is for ISSUES — do not run it against a PR body

**And on the ISSUE side, a hand-authored bold heading instead of a `## ` section is itself a defect: it defeats BOTH the gate read and the tick seam.** `issue_body.section_body` finds sections by `## <name>` headings — a body that writes `**Acceptance criteria:**` (bold label, no `## `) has ZERO parseable sections, so `check-pr-acceptance` reads zero criteria and passes green-on-a-holds-closes, while `acceptance_writeback.tick_acceptance` raises `BodyError` because it cannot locate the criteria block to tick. The canonical headings are `## Problem` / `## Why it matters` / `## How we fix it` / `## Benefit` / `## Acceptance criteria` / `## Technical` (+ optional `## Not covered`), in that order, each a real `## ` heading with the criteria as `- [ ]` boxes.

- **Re-render is a planner-Ok body edit of the issue, not a code change and not a peer-lane touch.** Before PATCHing, validate the re-render against the repo's own parser (`git show origin/main:scripts/issue_body.py` — import and call `missing()` on the new body; expect an empty list) rather than eyeballing heading shapes. Preserve the original criteria TEXT and any out-of-scope items; the heading markup changes. **But convert the criteria LIST markup to `- [ ]` checkboxes in the same pass — a restate that keeps the source's numbered `1. 2. 3.` list still fails `missing()` with `## Acceptance criteria` carries no `- [ ]` item (issue #745), and the tick seam cannot tick a numbered item.** "Verbatim" applies to the measured outcome in each criterion, NOT to its list marker: pull each numbered line's text unchanged into its own `- [ ]` box. Check the box count (`grep -cE '^- \[ \]'`) equals the criteria count AFTER the PATCH on the fetched live body, not just on your draft.
- **Confirm it took by heading count, not prose:** `gh issue view <n> --json body --jq '.body' | grep -cE '^## '` should equal the section count (six, or seven with `## Not covered`), and the unticked-box count should match the criteria you preserved. A body edit fires no CI run, so the next fresh push is what re-evaluates the now-parseable criteria.
- This is the ISSUE-side sibling of the PR-body rule below: a PR body legitimately uses different prose headings, but an ISSUE body must use the canonical `## ` sections or nothing can read it.
- **`## Technical` MUST be the LAST section, and `## Out of scope` is NOT a valid heading — a body that ends with a natural `## Out of scope` tail reds `missing()` with TWO errors, not one.** The validator rejects a body whose `## Technical` is followed by any other `## ` heading, and names every heading outside the six canonical (plus optional `## Not covered`) as `unknown section(s)`. So a tracker written with an out-of-scope tail reports both `` `## Technical` must be the LAST section (it is followed by `## Out of scope`) `` and `` unknown section(s): `## Out of scope` `` even though every canonical section is present. Fix by **folding the out-of-scope bullets into `## Technical` and deleting the heading** — keep the bullets, drop the section. Do not read the two errors as two separate defects and stop; it is one structural fix.
- **PATCH the body from a FILE (`-F body=@/tmp/body.md`), never an inline shell variable.** An issue body's quotes and backticks ("`## Problem`", `` `origin/main` ``) break `bash -c` command substitution — the inline `python3 -c "...$(echo "$B" | sed ...)"` pattern dies with `syntax error near unexpected token`. Write the canonical draft with `write_file`, gate it, then `gh api -X PATCH repos/<o>/<r>/issues/<n> -F body=@/tmp/body.md`. `-F body=@file` is the only form a backtick/quote-heavy body survives.
- **Re-gate the FETCHED live body after the PATCH, not the draft file.** `gh issue view <n> --json body --jq .body > /tmp/live.md` then run `missing()` on `live.md` — `missing: []` on the draft proves only that you authored a good string, not that GitHub stored it (a partial PATCH or a later bot edit can differ). Also count a preserved evidence anchor (`grep -c` on a sha or comment-id you folded in) to prove content loss was zero.

`scripts/issue_body.py::missing()` checks an **issue** body for the six canonical headings (`## Problem` /
`## Why it matters` / `## How we fix it` / `## Benefit` / `## Acceptance criteria` / `## Technical`). A **PR**
body is a different artifact and legitimately uses different prose headings — `## What & why`, `## The fix`,
`## Acceptance`, `## Evidence`, plus the `BASE:`/`AGENTS:` lines. Running `issue_body.missing()` on a PR body
therefore reports all six "missing" and reads as a body-gate failure — it is not. This is a false red you
manufacture yourself, and asserting it to a lane sends it chasing a reformat that no CI check asked for.

- **Assert a PR-body defect only when a NAMED CI check fails on it.** The PR-body gate is `check_pr_hygiene.py`
  `pr-body` (empty/placeholder/serialized-object) plus `check-pr-closing` (adjacent close) — not the six-section
  issue validator. Read the failing step name (`gh api …/jobs/<id> --jq '.steps[]|select(.conclusion=="failure")|.name'`)
  and name THAT; never infer a body defect from a heading shape a PR does not owe.
- **To sanity-check whether a PR body reds anything, run `gh pr checks <n>` — not `issue_body.missing()`.**
  Two reds (`guard`=`check-pr-closing`, `ci-verdict`=downstream) are the real defects; a heading-shape complaint
  is your own tooling, not the repo's.

## The PATCH is not the fix — the gate is

A body patched by hand is a one-off. File an issue to extend `check_pr_hygiene.py` `pr-body` (and
its comment path) to **fail a serialized-object body/comment**, with the real JSON body captured as
a hermetic regression fixture, plus wiring so `make check-wiring` stays green. Shape it in the
six-section form, label `agent:implement`, and route it through the **normal implement queue** — the
planner files and dispatches, the lane implements the gate. Do not silently patch the body and move
on: without the gate, the next lane repeats it.

- A serialized body passes **both** `pr-body` and `check-pr-closing` green, so CI cannot be trusted
to catch it — detection is a manual read of `.body`, not a check to wait on.
- Keep the fix scoped to `check_pr_hygiene.py` + its tests + wiring; do not widen into auditing
already-merged bodies (that is a separate issue).

## A required literal comes from the enforcing script, not from plausibility

When a gate demands an exact body line (the preflight `AGENTS: <sha> <bytes>b <lines>l` record), never
paraphrase it into a plausible form (`AGENTS: read at <sha> (origin/main)`). A near-miss literal is an
instruction the lane cannot satisfy and a green it can never reach; the enforcing code's own format
string is the only authority, and the numbers are a measurement:

```bash
git -C <repo> show origin/main:scripts/bot_preflight.py | grep -n 'AGENTS:'   # the f-string = the exact shape
git -C <repo> show origin/main:AGENTS.md | wc -c; git show origin/main:AGENTS.md | wc -l   # bytes / lines
```

Paste the derived line into the PR note, so the lane copies it rather than reconstructing it.

**The planner may apply the `AGENTS:`/`BASE:` preflight record to ANY lane's PR body directly — it is a measurement of `origin/main`, not lane authoring.** Unlike the `SYNC:` line (which names the profile-owning lane and requires that lane to re-sync the live profile, so it stays lane-owned), the `AGENTS:`/`BASE:` pair is a content-free record of the current main tip and AGENTS.md metrics — byte-identical regardless of who pastes it. When a PR is otherwise blocked only on this stamp and its owning lane is not actively editing the body, compute the record and PATCH the body with the author token yourself rather than dispatching and waiting: the owner's rule is never to wait on a lane for a mechanical fix. Announce it in a PR comment so the trail exists, and prove it by re-running the gate against the fetched body.

```bash
MAIN=$(git -C <repo> rev-parse origin/main)
B=$(git -C <repo> show "$MAIN":AGENTS.md | wc -c); L=$(git -C <repo> show "$MAIN":AGENTS.md | wc -l)
gh pr view <n> --json body --jq .body > /tmp/pb.md
# strip old AGENTS/BASE lines, INCLUDING the unterminated `<sha> <n>b` stragglers some lanes leave
# (regex must tolerate the missing ` <lines>l` terminator or the old line survives and you get two AGENTS:)
grep -vE '^AGENTS: [0-9a-f]{7,40} [0-9]+b( [0-9]+l)?$' /tmp/pb.md \
  | grep -vE '^BASE: [0-9a-f]{7,40} \(== origin/main at' > /tmp/pb.clean.md
{ printf 'AGENTS: %s %sb %sl\nBASE: %s (== origin/main at open)\n\n' "$MAIN" "$B" "$L" "$MAIN"; cat /tmp/pb.clean.md; } > /tmp/pb.new.md
gh pr edit <n> --body-file /tmp/pb.new.md
python3 scripts/check_pr_hygiene.py agents-line --head <head> --base "$MAIN" --body-file /tmp/pb.new.md   # expect OK
```

- **You CANNOT stamp the CURRENT main sha onto a STALE-base PR — but you CAN stamp it with the COMMON ANCESTOR.** `check_pr_hygiene.py agents-line` requires the cited sha to be an ancestor of BOTH head AND base, so a PR cut from an old base fails on the base side when you paste current `origin/main`. The instinct "stale base ⇒ rebase first, stamp after" is right about the *final* stamp but wrongly implies nothing can be done now: citing the **merge-base** (the old base, which is ancestral to both sides) validates OK and unblocks the PR's body gate while the lane-owned rebase is still pending. Measure which sha qualifies per PR and pick it explicitly — do not guess between "old base" and "current main":

```bash
MAIN=$(git rev-parse origin/main)
HEAD=$(gh pr view <n> --json headRefOid --jq .headRefOid)
for sha in "$MAIN" "$(git merge-base "$HEAD" "$MAIN")"; do
  if git merge-base --is-ancestor "$sha" "$HEAD" && git merge-base --is-ancestor "$sha" "$MAIN"; then
    echo "use candidate: $sha"   # $MAIN only if CURRENT; else the merge-base
  fi
done
```

After the lane rebases onto the new tip, the stamp is re-measured once more (that is the only rewrite owed), so say which sha you used and why in the PR comment — otherwise the next reader sees a "stale" stamp and re-does the whole derivation.

```bash
git merge-base --is-ancestor "$MAIN" <head> && git merge-base --is-ancestor "$MAIN" <base> \
  && echo stampable || echo "stale base — use the merge-base sha, re-stamp after the rebase"
```

- **A body edit fires no CI run** (see the body-only-edit section below): after the stamp, the old `guard`/`ci-verdict` row stays `failure` bound to the pre-fix run. Re-run it (`gh run rerun <id> --failed`) so the corrected body is re-evaluated — the stamp alone leaves the PR reading red.

**The `AGENTS:` sha must be a COMMIT, not the `AGENTS.md` blob sha — the gate resolves `<sha>^{commit}` and a blob never does.** The tempting derivation is `git rev-parse <base>:AGENTS.md`, which yields the blob object of the file; pasted as `<sha>` it fails with the gate's own verdict "the `AGENTS:` line cites <sha>, which is not a commit in this clone" even though the body visibly carries a well-formed line. Cite the **last commit that touched `AGENTS.md`** reachable from the base instead, and verify it is ancestral to both sides before handing it over:

```bash
git show <base>:AGENTS.md | wc -c; git show <base>:AGENTS.md | wc -l          # bytes / lines for the record
git log --oneline -1 <base> -- AGENTS.md | awk '{print $1}'                     # the COMMIT sha to cite
C=$(git log --oneline -1 <base> -- AGENTS.md | awk '{print $1}')
git merge-base --is-ancestor "$C" <base> && git merge-base --is-ancestor "$C" <head> && echo "cite AGENTS: $C"
```

Then confirm the head carries the same `AGENTS.md` blob (`git rev-parse <head>:AGENTS.md` == `<base>:AGENTS.md`) so the cited commit is genuinely reachable from both — otherwise the ancestry check is measuring a different file version than the record claims.

**A markdown-mangled literal fails even though the line visibly looks present.** The gate regex is
anchored at line start: `^AGENTS:\s+([0-9a-f]{7,40})\s+(\d+)b\s+(\d+)l\s*$`. An editor that
"formats" the record breaks the anchor and the match returns `None`, producing the misleading
"no `AGENTS:` line" verdict on a body the author can plainly see *does* carry one. The two manglings
seen: wrapping it bold (`**AGENTS:** <sha> …`) so the line begins `**AGENTS:` not `AGENTS:`, and
appending a trailing annotation (`AGENTS: <sha> <bytes>b <lines>l — 37 headings`) so it no longer ends
at `l`. The literal must be plain, unwrapped, and end exactly at `l`. When a guard says "no AGENTS
line" on a body you can see carrying one, grep the raw body for the anchored regex before believing
it:

```bash
# the gate is reproducible locally against a fetched live body — this is the verifying probe
gh api repos/<o>/<r>/pulls/<n> --jq '.body' > /tmp/body.md
git -C <repo> show origin/main:scripts/check_pr_hygiene.py > /tmp/cph.py
python3 /tmp/cph.py agents-line --head <head> --base origin/main --body-file /tmp/body.md; echo rc=$?
# rc 0 = the body passes the gate (red is stale/elsewhere); rc 1 = the body itself fails, stderr names why
```

A `rc 0` here proves the body is correct **now** and any remaining red is a bound-to-older-run artefact
(see the body-only-edit section below), not a content defect.

**The local repro must FETCH the actual head and base shas into the scratch repo first — an unfetched head silently grades the wrong tree and returns a false `rc 0`.** When you extract a tree with `git archive origin/main` into a scratch dir and then run the gate with `--head <head_sha> --base <base_sha>`, those shas do not exist in the fresh scratch repo unless you `git fetch` them in; the gate falls back to its default ref (the scratch `HEAD`, i.e. `origin/main`), so a body that actually FAILS at the real head can return `rc 0` — the exact false green that makes you tell the owner a red PR is fine. Fetch both shas into the scratch repo and confirm the gate resolved them (a `fatal: couldn't find remote ref` on the fetch is the tell that the repro is invalid) before believing any `rc 0`.

## A bot PR that changes `agents/<profile>/` owes a `SYNC:` line — a body edit, not a code defect

`check-pr-sync-line` is the sibling of the `AGENTS:` gate: a bot-authored PR whose diff touches
`agents/<profile>/` must report that the live profile was re-synced from the tree, one line per changed
profile, in this exact shape:

```
SYNC: <profile> make sync-agent-profile PROFILE=<profile>
```

The enforcing regex is `^SYNC:\s+([A-Za-z0-9_-]+)\s+make sync-agent-profile PROFILE=\1\s*$` (read it from
`git show origin/main:scripts/check_pr_hygiene.py`, `SYNC_LINE`). The back-reference means **the profile name
must match on both sides** — `SYNC: llgenie-engine-improver make sync-agent-profile PROFILE=engine-improver`
reds. Two profiles changed ⇒ two lines, one each.

- The failing step is literally `make check-pr-sync-line` inside the `guard` job, and the log prints
  `this PR changes agents/ under \`<lane>\` — the owner's propagation rule (#1724) requires the
  profile-owning lane to re-sync the live profile and report it: add a \`SYNC: <p> make sync-agent-profile
  PROFILE=<p>\` line for each changed profile`. It even names the line to add — quote it, don't theorise.
- **This is a body-only fix by the PR's owning lane.** No commit changes, no rebase: the diff is fine and
  the gate is reading the body. Dispatch the lane to add the line, never patch another lane's PR body
  yourself. Because it fires only on `agents/` diffs, a docs-only PR never sees it — don't pre-emptively
  add SYNC lines to one.
- **Preflight-blindness class (measured 2026-11-05): `check-pr-sync-line` can only run in CI** — it reads
  the LIVE PR body (`Makefile:1102` "the guard jobs call it with the LIVE PR body, never from a hermetic
  chain"), so it is unreachable from `make bot-preflight` (closes Hermetic: records `AGENTS:` via
  `bot_preflight.py`, never the SYNC gate). Consequence: a profile-touching lane opens a PR that is green
  on `make bot-preflight`/`check-docs`/`lint` yet **red-CI** on the SYNC line — three consecutive profile
  PRs caught exactly this (#1778 engine, #1779 security, #1780 pr-reviever), each burning a CI cycle on
  the same one-line body omission. When a profile-touching PR arrives, **do not trust the lane's green
  local checks** — the SYNC gate is CI-only and the lane could not have validated it: read the body's
  SYNC line against the regex yourself (`gh pr view <n> --json body --jq '.body' | grep -E '^SYNC:'`)
  BEFORE accepting, and dispatch the line proactively. Fixing the root = extend `bot-preflight` to
  flag `agents/<profile>/` diffs without a SYNC line (filed #1782 → ci-pipelines, preflight owner #792);
  the CI gate's own contract is correct (three reds prove it) and is out of scope.
- **A lane can MISATTRIBUTE the guard red to a separate drift and call the SYNC line done — attribute by the failing STEP name, not the lane's framing (#1785, docs-maintainer, measured 2026-11-05).** The lane reported "one measured blocker: box #2 sync CHECK=1 reds on pre-existing docs-maintainer tree/live drift, out of my scope" — a real, separate item, but NOT what was redding CI. The wire showed `guard`=failure with failing step `make check-pr-sync-line` and a body carrying only `AGENTS:`/`BASE:` (no `SYNC:` line). A whole-profile byte-identity drift (box #2) and the missing SYNC line are DIFFERENT gates: the first needs a docs-lane fold, the second is a one-line body edit in the PR's own vehicle. When a lane offers a plausible out-of-scope blocker, read the failing step (`gh api …/jobs/<id> --jq '.steps[]|select(.conclusion=="failure")|.name'`) and grep the body for `^SYNC:` — if the step is `check-pr-sync-line` and the line is absent, the blocker is the lane's own body omission, not the drift it named. Say "your acceptance work stands, but the red is the SYNC line you were dispatched to carry" so it fixes the right thing.

## Preflight PARITY: a preflight that RECORDS a body line is not one that VALIDATES the body carries it

`make bot-preflight` can compute and *emit* every required hygiene line into `preflight.txt`
(`bot_preflight.py` derives the `AGENTS:` record and the `BASE:` companion at the measured origin/main)
while **never checking that a would-be PR body actually cites them** — so a PR opens green on preflight
then reds `check-pr-agents-line` the moment CI's guard reads the live body. The tell: a PR whose body
carries **zero** hygiene lines yet reported green preflight. This is the general class behind every
body-gate, not just the SYNC line: AGENTS, BASE, SYNC, and closing are each discovered only by the CI
guard (all read the LIVE PR body, `#1589`), so preflight is blind to all of them until one is taught to
run the gate's own findings function over a *prospective* body.

- **The fix pattern (per gate, not one-off bodies):** reuse the enforcing script's own findings function
  (`check_pr_hygiene.agents_line_findings`, `pr_sync_line_findings`, the closing check) over a supplied
  `BODY=<path>` and refuse (exit 1) on a missing/mis-cited line; warn loudly (exit 0) when no body is
  supplied yet. Import the gate's function — never restate the regex — so preflight and CI cannot drift.
  One line-family per issue (SYNC was one; AGENTS/BASE is the sibling, likely a fresh issue routed to the
  preflight owner).
- **Do not trust a lane's "preflight green" when its diff touches `agents/` or adds hygiene-bearing
  content** — preflight proves record-currency, not body-compliance. Read the body's own lines against
  the gate regex before accepting, and dispatch the missing line proactively.
- **A green rulebook record is not a green body.** `AGENTS:`/`BASE:` in `preflight.txt` means the tree at
  the fetched tip is current; it says nothing about whether the PR body the lane will paste cites those
  values. Treat the two as independent facts and verify the body separately.

## A green PR with the line missing is a question, not a conclusion

When several open PRs' bodies all lack the `AGENTS:` line and CI is green on them, do not jump to
"the gate is unwired" off a bare `.github/workflows/` grep: `check-pr-hygiene` is a leaf target that
the workflow-invoked composites (`ci-unit`, and the `guard`/`scope` jobs) chain from the Makefile, so
the direct grep can be empty while the gate is live (see `ci-gate-vs-live-pipeline.md`). Resolve why
the live gate did not fire — bot-author detection, PR-body context unavailable in a push-run, or a
newly-added gate not yet in the classifier — and only then file. State the measured mechanism.

**Measure each PR in an enumerated claim separately, at filing time.** A list like "#A, #B, #C all lack
the line" is one claim per id, and lanes move heads: the one you flagged first may have pushed a fix
already. Scan each body against the enforcing regex and record the counts in the issue:

```bash
for n in <ids>; do
  gh api repos/<o>/<r>/issues/$n --jq '.body' | grep -cE '^AGENTS: [0-9a-f]{7,40} [0-9]+b [0-9]+l' | sed "s/^/#$n: /"
done
```

If a filed issue turns out to list an instance that is already fixed, post a CORRECTION comment on it
(the evidence list only; say the diagnosis is unchanged) rather than editing quietly — the issue is
the record other lanes route from.

## A newly merged gate retro-reds every open PR written before it

Merging a gate-wiring PR is a **board-wide event**, not a single-PR fix. The preflight record is a
snapshot: a body carrying `AGENTS: <sha> …` / `BASE: <sha> (== origin/main at open)` pins the main tip
that existed when the lane opened it. A PR opened before the new gate landed cites an older sha, and the
now-live gate derives its expected value from **current** `origin/main` — so the PR reds by design even
though its content is fine, and even after whatever real defect it has is fixed.

On every pass that observes a gate-wiring merge on main, re-measure all open PRs and post the finding on
the PR thread (not only in the dispatch DM):

```bash
gh api repos/<o>/<r>/commits/main --jq '.sha'                          # current expected sha
gh pr view <n> --json body --jq '.body' | grep -E '^(AGENTS|BASE):'   # what the PR claims
```

A mismatch means the vehicle owner must re-run `make bot-preflight` at the current tip, update the
body's `AGENTS:`/`BASE:` lines, and re-push. Say so explicitly and leave the PR OPEN — do not read the
retro-red as a content defect, and do not report it as a stale base when the base is otherwise fine.

**After a rebase clears `check-pr-base`, the body lines drift — whether that is a hygiene ask or a real red depends on ANCESTRY, so measure it, never assume.**
A rebase moves the merge-base to the current tip (clearing `check-pr-base`), but the lane usually does
not re-read the body, so `AGENTS:`/`BASE:` still cite the *open-time* sha. If that old sha is still an
**ancestor of the head**, the `AGENTS` ancestry gate tolerates it: the guard passes and CI is green
despite the body claiming a base that is no longer the base — a *drift/hygiene* correction naming the
citation→actual mismatch and asking for a fresh `make bot-preflight` paste, not a red. But a rebase that
**re-authors** the branch's commits (force-push with rewritten subjects) changes the head's parent chain,
so the old base sha may no longer be an ancestor of the new head — then the same stale body line is a
**real red on `check-pr-agents-line`**, not a tolerant pass. Decide by measuring ancestry, not by assuming:

```bash
git -C <repo> merge-base --is-ancestor <cited_sha> <head> && echo 'ancestor → hygiene drift' || echo 'NOT ancestor → real red, body must re-measure'
```

When it IS a real red, hand the lane the measured replacement rather than the instruction: `git show <new_base>:AGENTS.md | wc -c` and `| wc -l` give the exact bytes/lines to paste into a fresh `AGENTS: <new_base> <bytes>b <lines>l` / `BASE: <new_base>` pair. Read the body yourself rather than trusting a lane's "re-read confirmed": a rebase-done message often precedes the body edit.

**Before telling the lane to re-paste `AGENTS:`, check whether `AGENTS.md` is even the same blob at both bases — if it is, the `AGENTS:` line stays valid through the rebase and only `BASE:` needs the update.** A rebase changes the base sha, so the instinct is to re-measure AGENTS; but if no merged PR touched `AGENTS.md`, its content (and therefore its bytes/lines/record) is identical at the old cited base and the new base, and re-measuring is pure churn the lane will act on. Prove identity in one shot:

```bash
git -C <repo> rev-parse <old_base>:AGENTS.md  <new_base>:AGENTS.md   # same blob sha == unchanged
```

Same blob sha ⇒ keep `AGENTS: <old_base> …` verbatim (ancestry gate tolerates it — old base is an ancestor of the new head), and the only body edit is `BASE:` → the new tip. Different blob ⇒ re-measure bytes/lines as above. State which case you measured so the lane does not "fix" a line that was never broken.

**A body-only edit fires no CI run — the old red stays bound to the old run until a re-run or a push.**
Editing the PR body to add/fix the `AGENTS:`/`BASE:` lines creates no commit, so no fresh `pull_request`
run is triggered: the `guard`/`ci-verdict` rows stay `failure` and `ci-verdict` keeps its output pinned to
the *pre-fix* run ("`ci-verdict: red (run <old>)`", "no verdict"). The body is now correct and the PR still
reads red — do not conclude the fix failed or that a code defect remains. Verify by comparing the run the
verdict names against the body's current content: if the verdict is grading an older run than the edit, the
remedy is `gh run rerun <old_run> --failed` (or a trivial commit push) so a runner re-evaluates the corrected
body — name that as the last step, not another body edit.

**After the re-run, the guard JOB concludes success while the overall RUN can stay `in_progress` for many minutes — read the JOB's own conclusion and step list, never the run status.** A body-reading gate (`check-pr-acceptance`, `check-pr-agents-line`, `check-pr-closing`, `check-pr-sync-line`) runs inside the `guard` job, but the run keeps `status: in_progress` while its heavy/`skipped` cells (linux/unit, ci-images) are still settling or queued behind `needs:`. Polling `gh run view <RUN> --json status,conclusion` therefore reads `in_progress` long after the gate has already banked its verdict — reporting "not yet green" there is false, and waiting for run-completion burns the turn. Read the `guard` job directly and confirm the acceptance step itself completed `success`:

```bash
# trigger the re-run, then poll the GUARD JOB's conclusion, not the run's
gh run rerun <RUN> --failed
gh run view <RUN> --repo <o>/<r> --json jobs --jq '.jobs[]|select(.name=="guard")|{s:.status,c:.conclusion}'
# step-level proof once the job is completed: the acceptance step must be success, not skipped
gh api repos/<o>/<r>/actions/runs/<RUN>/jobs \
  --jq '.jobs[]|select(.name=="guard")|.steps[]|select(.name|test("check-pr-acceptance"))|{n:.name,c:.conclusion}'
```

A `guard` job `completed/success` with `step check-pr-acceptance = success` IS the banked green — quote the run id + job id + step name as the objective evidence, and say the run-level `in_progress` is the still-settling heavy rows, not a missing verdict. (This is the green-side sibling of "a concluded cell's log is readable inside an in_progress run" in `actions-job-log-reading-midrun.md`; do not re-run again just because the run object has not flipped to `completed`.)

**After the fix rerun goes green, a `group_by(.conclusion)` rollup STILL shows `failure:1` — the stale
pre-fix check-run is a separate object at the same head, not cleared by the new run.** Once the corrected
body re-runs `guard`/`scope` to success, the head has TWO check-runs of some names: the old failed one and
the new passed one. `gh api .../commits/<head>/check-runs --jq 'group_by(.conclusion)|…'` counts both, so it
reads `success:13, failure:1` and looks like an unfixed defect. Reconcile by NAME and `completed_at`: the
`failure` entry is the older, superseded run (an old `ci-verdict` bound to the pre-fix body run); the
`success` entry of the same name at a later timestamp is the trustworthy verdict. Say "stale check-run at the
same head, superseded" and name its timestamp, not "one red remains." Get per-name+time with
`… --jq '(.check_runs//.)[]|{name,concl:(.conclusion//.status),at:(.completed_at//.started_at)[11:19]}'`.

**An ASYMMETRIC guard verdict — same sha, some `guard` runs pass, one fails — is a body-timeline
tell, not a flake.** When sibling `guard` check-runs at one head disagree, reconcile the body's
`updated_at` against each run's start time. A body edited *between* a passing run and a failing rerun
explains it exactly: the passing run read the old body, the rerun read the edited one. The failing run
is the **newer** read and is trustworthy; the passes are stale. Confirm from the API, not job logs:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.updated_at'          # when the body last changed
gh api repos/<o>/<r>/actions/runs/<id> --jq '.run_started_at,.created_at'
```

If `updated_at` falls after the passing run and before the failing one, the edit is the variable — do
not call it transient, and do not "re-run to clear the flake": the body must be corrected first, then
re-dispatched (a body edit alone fires no run, above).

Re-sweep main's tip for **new unapproved merges** in the same step: merge velocity on this board is
minutes, so a tip measured earlier in the same pass is already history.

## An administrative gap is not the whole red

Before telling an author a PR "only needs" the body line, run `gh pr checks <n>` (or the jobs API) and
name every failing job and the failing step. The missing `AGENTS:` line and a failing gate are
independent: one head can lack the line and still be red on `linux / lint` and `scope` — both of which
execute `make ci-lint` (the markdown linefeed/editorconfig gate), so expect the same root cause reported
twice under different job names:

**But `scope` also runs `check-pr-agents-line`, and a body with NEITHER line reds three checks from one
cause.** When the body has no `AGENTS:` line at all, `guard` fails `no AGENTS:` AND `scope` fails the same
target (`make: *** [Makefile:…: check-pr-agents-line] Error 1`), and `ci-verdict` then reports "run has no
verdict / N job(s) unaccounted for" as a *downstream consequence* of guard not publishing a verdict — not
a third defect. So for a body-less-lines PR, read each failing job's own log and attribute: guard = body line,
scope = check-pr-agents-line (NOT automatically linefeed), ci-verdict = downstream. Do not tell the lane to
append a trailing newline on a PR where `scope` failed on the agents-line target; that is a phantom fix that
leaves the PR equally red. Conversely, when the body already carries AGENTS and only `linux/lint`+`scope`
red on `LINT FAIL` named paths, it IS the linefeed family. The discriminator is the failing step's log line,
never the check name.

**An aborted `scope` job reports only its FIRST failing step — `scope`=agents-line is conditional on ci-lint
passing, so read the step list, not the job name.** `scope` runs `make ci-lint` FIRST; when a changed file (e.g. a
`docs/changes.d/<date>-<slug>.md` change-note fragment) is missing a trailing newline, ci-lint fails and every
later scope step — `check-docs`, `check-wiring`, `check-issue-bodies`, `check-pr-closing`,
`check-pr-agents-line`, `check-pr-sync-line` — reads `skipped`. `guard` runs a DIFFERENT order
(`check-git-identity` → `check-pr-authors` → `check-pr-closing` → `check-pr-agents-line` → …), so it reaches and
fails check-pr-agents-line. On a head carrying BOTH a lint defect and a missing `AGENTS:` line the two jobs
therefore name DIFFERENT roots: `guard`=agents-line, `scope`=ci-lint (agents-line `skipped` inside scope, NOT
the red), `ci-verdict`=downstream of both. Never infer `scope`=agents-line from the job name when AGENTS is
absent — a `skipped` later step is not the failure:

```bash
gh api repos/<o>/<r>/actions/jobs/<job_id> --jq '.steps[]|"\(.conclusion // "n/a")  \(.name)"'   # the FIRST `failure` is the root; a `skipped` step below it is not
```

Hand the lane BOTH measured fixes in one message (the newline on the named fragment AND the `make bot-preflight`
AGENTS line) so one re-push clears both — fixing only the apparent one leaves the PR equally red on the other.

```bash
gh pr checks <n> --repo <o>/<r>                       # which jobs are red at this head
gh api repos/<o>/<r>/actions/jobs/<job_id> --jq '.steps[]|select(.conclusion=="failure")|.name'
```

List the real red first, the body line second; otherwise the lane fixes the body and the PR stays red.
When your own earlier comment carried an inexact literal or a partial red, post a **CORRECTION** that
names it as superseded and restates the exact values — an imprecise instruction left standing is acted on.

## Measure gate likeness from `origin/main`, never the working tree — a stale tree fabricates a false "rule doesn't exist"

The planner refuted a lane's `BASE:==AGENTS:` correction by reading `scripts/check_pr_hygiene.py` in the
**primary-checkout working tree** and posting "the file is 509 lines; there is no equality rule." The canonical
`git show origin/main:scripts/check_pr_hygiene.py` blob is **813 lines** and its line 572 is literally
`if mb.group(1) != sha:` — the `base-line` gate (#845) that holds `BASE:` to the SAME sha the `AGENTS:` line
cites. The 509-line working copy is ~44 behind origin/main (owner-mediated lag), a false-grounding trap the
whole rulebook warns about but which still bit a gate-verdict. Consequences: (1) I reversed a correct lane
correction based on a fabricated read; (2) `AGENTS: <old-md-touch> + BASE: <base>` looks plausible (#792
ancestry passes) yet reds `base-line` on any re-run — only `AGENTS==BASE==<rebase-onto>` is valid. So:

- When a lane cites a specific line/rule in a gate script, verify against the **`git show origin/main:<path>`**
  blob — never `wc -l <path>` on the working tree, never `grep` on `scripts/` in the checkout.
- A plan the planner ships that disputes a lane's measured gate quote MUST carry the `origin/main` blob length
  and the quoted line, so a stale tree cannot silently falsify it.
If the planned research later measures the REAL blob and the lane was right, post a **withdrawn CORRECTION**
naming the earlier comment id as superseded and conceding — an un-withdrawn wrong refutation (a) teaches the
lane its own memory is unreliable and (b) lets the next lane cite the false "no rule" in its own defense.

## Restating a whole ticket FAMILY: generate, do not hand-edit N bodies

A gate-failing family (dozens of sibling tickets sharing one non-canonical skeleton — `## Problem` /
`## Proposal …` / `## Acceptance …` / `## Ownership` / `## Related`) is ONE structural defect, not N.
Hand-authoring each cousin is where content silently diverges; instead run
`scripts/restate_issue_canonical.py` once per issue: it reads the ORIGINAL body, derives the
per-ticket token and the per-ticket criterion, and emits the canonical skeleton around them.

- **The per-ticket criterion must be DERIVED from its own body, never shared across cousins.** Two
  siblings with the same skeleton have different middle criteria (one proves a real network reach, one
  proves exactly-one-PR-never-merge, one proves a dispatch path). A template that copies one cousin's
  criterion into all of them reads as a restate but asserts the wrong acceptance — a defect the gate
  cannot see, because `missing()` only checks heading shape and box presence. After generating, print
  and eyeball criterion 2 per issue.
- **Gate locally, post, then re-gate the LIVE fetched body — per issue.** Local `missing()` on the draft
  proves only that you authored a good string; GitHub stores what it stored. Loop `gh issue edit --body-file`
  then `gh issue view --json body` and re-run `missing()` on the fetched text, asserting `## Technical`
  is the last heading and the `- [ ]` count matches. A batch post with no per-issue live re-gate leaves
  any single silent failure invisible.
- **Batch the posts in one loop, but keep the verification per-issue.** One `for n in …; do gh issue edit …`
  pass is fine; the check that matters is the second pass over the fetched bodies.
- **Classify before you start: not every open ticket is gate-failing.** Read `missing()` output rather
  than assuming the whole family is broken — a sibling already restated, or one carrying an honest
  `verify`-comment ledger, needs no rewrite, and re-posting over it destroys the ledger's context.
