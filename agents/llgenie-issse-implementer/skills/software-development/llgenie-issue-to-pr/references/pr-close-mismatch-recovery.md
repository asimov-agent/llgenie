# Recovering a PR that went RED on the close+mismatch+fresh-base trio (issue #1716-class)

When a PR body/naming defect reds the guard, diagnose against THREE independent gates — fix all three together before pushing:

1. **Plain literal `closes #N` must be present and ONLY in the body** (gate regex `\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)(?![#\w])`). VERIFY THE WHOLE BODY, not just that the number appears: prose like a "→ red" example bullet that literally says `closes #1707` parses as a REAL close, so a body that names the fix (closes #1716) AND mentions an old example close (#1707) reds as `squash-commit`/`squash-mismatch`. Run `scripts/check_pr_closing.py report --body-file <body> --base origin/main --rev HEAD --cwd <wt>` and assert the closing set is EXACTLY `['N']`; grep for every `close`/`fix`/`resolve` + `#` adjacency and reword incidental mentions ("names #1707", "carries only `(#1707)`"). The nastiest case is a *historical explanation* — e.g. explaining a past bug with "a merged PR's `closes #1646` cleared the box" — which the gate reads as YOUR body closing #1646. Never write a close keyword adjacent to an issue you are not closing, even inside an illustrative sentence: reword to "that issue" / "an earlier merge-close".
2. **AGENTS-/BASE-line freshness** (`check-pr-agents-line`, #792): the body cites the literal `make bot-preflight` output at the base the PR was OPENED. If main moves after you opened, regenerate `AGENTS:`/`BASE:` (they change on every main advance) and push a fresh body — a stale line reds `check-pr-agents-line`. Both lines must sit FLUSH-LEFT at column 0 — the gate matches `^AGENTS:`/`^BASE:` with `re.MULTILINE`, so wrapping them in an indented code block, a `> ` quote, or a `- ` list item defeats the match and reds the gate with the same message as a genuinely missing line. Paste the preflight output verbatim, unindented.
3. **Branch cut from the LIVE base** (`check-pr-base`, #845): `merge-base(origin/main, HEAD) == origin/main` at the time CI runs. If main advanced after your rebase, rebase again onto the fresh tip; `git merge-base origin/main HEAD` must equal `origin/main`. But if a rebase/merge-conflict LANE owns the head, do NOT force-rebase it yourself: message that lane with the measured facts (head sha, current merge-base, live `origin/main` tip, and the "foreign commits" list — confirm they are YOUR own `closes #N` commits, i.e. nothing leaked) and post the same on the issue, then let them rebase-onto-tip + push-with-lease; head-independent evidence (a recorded run id, a completed sweep) survives the rebase, so the handoff costs nothing. Rebase on a branch another lane is working is a conversation first, not a do-it-yourself. After that rebase, the body's cited head sha is STALE even though the tree is byte-identical — regenerate the `AGENTS:`/`BASE:` lines (`make bot-preflight` at the new base, flush-left) AND rewrite every `## Verification` head-sha reference to the new head, labelled `(tree identical to <old-sha>)` so nobody thinks you re-measured. A rebase rewrites the sha exactly like an amend or squash: a count captured before it is not "at the current head".

**Read the live `^AGENTS:`/`^BASE:` line before replacing it, and assert the replace changed the body.**
The body ordinarily cites the base **at open** — an older sha than both the base you are rebasing onto
and the one you remember rebasing to — so a hard-coded `body.replace("AGENTS: <sha-i-assume>", ...)`
silently matches nothing and you then push a body that still reds `check-pr-agents-line` while
the edit step reported success. Always: (1) fetch the body and print the two lines (`gh pr view <n> --json
body --jq .body | grep -E '^AGENTS:|^BASE:'`) to learn the actual sha; (2) build the new body and
assert `new != old` in the same script, aborting loudly if unchanged; (3) `gh pr edit --body-file`, then
re-read the same two lines as the wire verification. Same rule for any other body field you rewrite by
string substitution (head-sha citations, `## Not covered` bullets) — an unasserted replace is an
unverified write.

Workflow that works (each step exits 0 before continuing):
- reconcile body close-set => `[N]` (report returns `closing references: #N` and `check` returns 0);
- `make bot-preflight` on a branch whose merge-base == origin/main tip; capture the literal AGENTS/BASE lines;
- re-edit the PR body (`gh pr edit`) — the guard reads the LIVE body (#1589/#1711), so a corrected body clears check-pr-closing/agents-line ON RE-RUN (they read the body live, not from an event snapshot);
- `git push --force-with-lease <fork> HEAD:<branch>` and `git ls-remote <fork> <branch>` must equal local HEAD;
- a push triggers a FRESH CI wave on the new head; let it conclude — `gh pr checks` shows the new runs.

Do NOT claim done until `gh pr checks` shows the unit job `status=completed conclusion=success` (or a proven-local green on identical content) AND every row is pass (no `fail`, no `pending`). Owner merges under #1088; never merge yourself — after a merge, verify `gh api pulls/<n> --jq '{merged,merge_commit_sha}'` and the issue `state: closed`.

## `check-pr-acceptance` vs `check-pr-closing`: dropping the close is a TRAP

`check-pr-acceptance` reds `a merged PR closes an issue whose acceptance criterion is unchecked` when the body closes `#N` but the linked issue's `## Acceptance criteria` still has `- [ ]` rows. The obvious remedy — delete `closes #N` from the body, or move it under `## Not covered` — does not clear the red, it SWAPS it: if ANY commit in the PR's range carries `closes #N` in its OWN message body, that commit-close is joined into the squash text, so §143 `commit_closed != body_closed` reds `check-pr-closing` as `squash-mismatch`. A body edit cannot clear an acceptance charge; the body must MIRROR the commit closes.

Diagnose before editing anything:
```
python3 scripts/check_pr_closing.py report --body-file <body> --base origin/main --rev origin/<branch>
# prints: closing references / referenced issues / squash closes / claims
```
If `squash closes` names the issue, the body MUST keep `closes #N` — do not touch the close line.

Then split the acceptance charges ITEM-BY-ITEM (read the guard log at the CURRENT head — a pre-fold log is stale):
- **satisfied-by-branch item** (the artefact exists in the tree — verify it: the workflow cap is matrix-aware, the change-note files are present, `make check-docs check-workflows check-wiring lint` each rc=0). Unticked criterion on a correct branch → cleared by write-back (`acceptance_writeback --proven`, #1644) after the verdict; NOT body-clearable and NOT waiting on any run.
- **run-gated item** ("a COMPLETED-SUCCESS run at the new cap is named") → waits on the verdict cell; still not body-clearable.

So a guard red after a correct fold is usually the DESIGNED self-red (unticked criteria on a branch that already implements them), clearing via write-back — never a body edit. Do not act on a planner's "drop `closes #N`" directive without running the report above: it is tree-falsified whenever a range commit carries the close.

### `claim-exceeds` and `claim-unchecked` are TWO different acceptance reds — the PR body's own checkboxes red the first

`check-pr-acceptance` compares the PR body's checkbox list against the closed issue's `## Acceptance
criteria`. A `## Verify` (or any) section that writes its steps as markdown task-list rows (`- [x] `/`- [ ] `)
is READ as CLAIMS about the issue's criteria, and reds **`claim-exceeds`** when the body ticks more itemsthan the issue has ticked. Fix: do NOT tick anything in the body — write the Verify evidence as plain prose
bullets or a fenced command block, never `- [x]` task-list rows, so the gate sees zero claims.
`claim-unchecked` (issue criteria still `- [ ]`) is the DESIGNED self-red cleared only by the reviewer's
`--proven` write-back (#1644/#1792) — not body-clearable. Do not confuse the two: `claim-exceeds` is your
own body defect and IS fixed by de-ticking the PR body; `claim-unchecked` is the reviewer-owned hold.

A THIRD class looks like neither: a criterion in the **ISSUE** body that is `- [x]` but carries an
empty `(proven: …)` — e.g. `- [x] <criterion>.` with no `(proven: reviewer=… run=… head=…)` after it.
The gate reads that as "a ticked acceptance criterion names no replayable run id" and reds. This is a
MALFORMED tick (a checkbox flipped without the evidence a real write-back attaches), not a genuine
verdict — and it is NOT fixed by un-ticking the PR body (that fixes only `claim-exceeds`). The remedy
is to UN-TICK the criterion in the ISSUE body (`gh issue edit <n> --body-file`, flipping that one row
back to `- [ ]`), assert the replace changed the body, and re-read the row on the wire. Only do this
when the criterion is genuinely UNPROVEN — an un-tick is the honest state, never a way to dodge a
criterion your diff actually satisfies. Check the issue timeline first: a real `--proven` write-back
lands as a comment with `(proven: …)`; an evidence-less `- [x]` has no such comment behind it. Then
let the PR body's `## Not covered` bullet naming the blocking issue carry it (the gate's other
sanctioned path), or wait for a real run+write-back.

### Give each AC a reproducible `command → rc → head sha` line so the reviewer can apply the verdict-gated write-back

A reviewer's `--proven` write-back needs evidence it can RE-RUN, not prose. Put one line per acceptance
criterion in the body: the exact command, its observed `rc`, and the head sha it was measured at — e.g.
`pytest tests/test_x.py::test_name -q  # rc=0 @ <head>` and `grep -c '<placeholder>' scripts/placeholder.py  # rc=1 @ <head>`.
A bare "tested, passes" gives the reviewer nothing to pin the `(proven: reviewer=… run=… head=…)` provenance
to; reproducible per-AC commands let the write-back land on the first pass instead of a round-trip. Beware:
the commands' own literals (`closes #1000`, a placeholder `closes #<n>`) are parsed by `check-pr-closing` —
keep any other-issue ref non-adjacent to the close verb (see the close-prose trap above).

### When the close must legitimately GO (test-only PR for an AC-demanding issue)

The inverse case: the PR's diff does NOT implement the issue's acceptance criteria (e.g. a test-only or doc-only branch that claimed `closes #N` for a product-behaviour issue). Here the correct remedy is to REMOVE the close, not keep it — but a body edit alone is insufficient: `check_pr_closing` requires `body_closes == squash_closes` (§143), and the head COMMIT MESSAGE still carries `(closes #N)`, so the gate keeps red as `squash-mismatch` even after the body is clean. Fix BOTH halves:
- **Edit the PR body to drop the `closes #N` line** (and note the issue under `## Not covered`), keeping `AGENTS:`/`BASE:` intact. A `gh api pulls/<n> --method PATCH` REPLACES the whole body, not one field, so build the new body from the FULL fetched body (`gh api … --jq '.body' > /tmp/b.md`, string-replace the one block, send the whole thing) and read back asserting all three invariants — new text present, `closes #N` absent, and the trailing `AGENTS:`/`BASE:` lines still present and flush-left (a naive replace on a mid-body section easily drops the tail and silently reds `check-pr-agents-line`);
- **Amend the head commit message** to drop the same close: `git commit --amend -m "<subject without (closes #N)>"` (content-lossless — verify `git diff <base> HEAD` is unchanged), then `git push --force-with-lease` (fetch immediately before). A `dcf82e74`-style body-only fix leaves the branch red; the amend is the half most often missed.
- Re-run the closing gate at the new head and read `rc`; only a `rc=0` proves body-close == squash-close == none.
- **Re-measure test/verification evidence at the NEW head, or say which old sha it belongs to.** An amend/squash rewrites the sha while the tree is byte-identical, so a suite count or a `pytest -v` tally captured before the amend is attached to the old sha and is NOT "at the current head". Either re-run it at the new head, or state explicitly "N passed, tree identical to `<old-sha>`" — never quote the pre-amend count as current-head evidence, and never assume a reviewer reads a sha-less count as current.
- **`file:line` citations in evidence go stale the moment YOUR fix inserts lines.** An evidence
  comment that pins a claim to `engine_image.py:L220` (written against the pre-fix head) points at
  unrelated code once the fix adds a helper above it — the same defect the comment was proving.
  Re-derive the line numbers at the current head (`grep -n <symbol> <file>`) and post the corrected
  citation with the head sha, or cite SYMBOL names instead of line numbers so the pointer survives
  the next edit. Never leave a line-pinned citation un-re-measured after a head move.
- **Sweep the body's `## Not covered` for a SUPERSEDED witness pointer.** When the evidence path moves (e.g. the AC witness becomes a narrow `push=false` dispatch instead of re-reading a locked anchor run's log), every bullet that still points at the old anchor run/job is a stale lock that sends the reviewer to a log that will never be readable. Replace it with the actual live evidence (run id + head sha + dispatch params) and post a one-line bookmark naming the correction; do not leave both paths in the body as if they were alternatives.

**Run the closing gate from the PR worktree, never the parent clone.** `check_pr_closing.py --rev HEAD` reads the CWD's git HEAD as the squash source; run it from the parent clone (checked out on an unrelated branch) and it validates that branch's commit message, not the PR's — producing a FALSE red or a false pass. `cd` into the PR worktree (or pass `--cwd <wt>`) and pass `--head <branch>` for the agent/* scope check.

### A `## Not covered` exemption bullet must be ONE line, starting `-` and ENDING in `#<n>`

The gate matches an out-of-scope waiver with the regex `^-.*\s*#\d+\s*$` against each bullet line — so
the bullet must be a SINGLE line that BEGINS with `-` and ENDS (last non-space token) with the bare
`#<n>` of the issue that covers the residual. A bullet wrapped across two lines, or one that puts the
`#<n>` mid-sentence followed by more words, does NOT match and the gate stays red even though the
waiver reads correctly to a human. Shape it as a single bullet whose final token is the issue
number, e.g. `- <the residual, one line> — tracked in #<n>`, with nothing after the number. Verify by
running `check_pr_acceptance.py check --body-file <body> --repo <o>/<r>` locally and asserting
`[check-pr-acceptance] OK` — a green local check is the proof the bullet parsed, not the visual read.

**There may be only ONE `## Not covered` section — the gate reads the FIRST match, and a second
section is silently ignored.** The extractor returns the first `## Not covered` section and never
concatenates a duplicate, so an exemption bullet placed under a SECOND `## Not covered` heading
does nothing and the criterion stays red while the body reads correctly to a human. When a body
grows a second such heading (one added earlier, another appended by a later edit), MERGE them into
a single section and re-run the local check to confirm the bullet now parses; grep the body for
`^## Not covered` and assert the count is exactly 1 before pushing.

**New files must end with a trailing newline, or `make lint` reds the final-newline check.** The
lint gate flags `no newline at end of file` on every freshly-created file — docs fragments under
`docs/changes.d/`, generated change notes, and every openspec file (`proposal.md`/`spec.md`/
`tasks.md`). A change that omits this reds guard AND scope on the trailing-newline step even
though the code change is correct. Before pushing any PR that adds files, append the missing
newlines (`printf '\n' >> <file>` / verify `tail -c1 <file>` is a newline) and re-run the lint
step to confirm `success` — do not assume it.

Reproduce the gate LOCALLY against the LIVE body before theorising (the checker CLI is `check --body-file`, NOT `--pr-number`):
```
gh api repos/<o>/<r>/pulls/<n> --jq '.body' > /tmp/live_pr_body.md
python3 scripts/check_pr_acceptance.py check --body-file /tmp/live_pr_body.md --repo <o>/<r>
# prints "[check-pr-acceptance] N violation(s)" + one line per unticked criterion
```
Confirm the violation count and every class is the SAME (unticked acceptance criteria), not a mixture with a real code/gate error. In the guard log the three check names `ci-verdict`/`scope`/`guard` are frequently ONE gate (`make check-pr-acceptance`) reported three times — read ONE failing job's own log and confirm before treating them as three separate defects.

### Prove WHICH gates passed on the wire — read the job's `steps[]`, not the run `conclusion`
The guard job is FAIL-FAST: once `check-pr-acceptance` reds, every later step (`check-pr-base`, `ci-slow-rows`, the scope publish, `ci-verdict`) shows `skipped`, and the run/job top-level `conclusion=failure` (plus the `statusCheckRollup` rows) hides that the gates BEFORE it — `check-pr-closing`, `check-pr-agents-line`, `check-pr-sync-line`, `check-pr-openspec-change` — each returned `success` at the same head. So the top-level `failure` is NOT evidence that your diff's gates fail. To know whether YOUR change is green on the wire (not merely on your machine), enumerate the steps of the failing job:
```
gh api repos/<o>/<r>/actions/jobs/<job_id> --jq '.steps[] | .number, .name, (.conclusion // "nil")'
```
A `success` row for the gate your diff was written to satisfy (e.g. `check-pr-closing`, `check-pr-openspec-change`) IS that gate's wire verification; the `skipped` rows below the fail-fast point are a consequence of the designed acceptance self-red, not of your change. Read the steps before diagnosing, and never treat `conclusion=failure` as 'my gates are red'.

Fetch the STEP verdicts, not the raw job log: `gh run view <run> --log --job <id>` and `gh api repos/<o>/<r>/actions/jobs/<id>/log` frequently answer `log not found` / HTTP 404 for aggregate and ancillary jobs (a verdict roll-up like `ci-verdict` exposes ZERO steps — it has no log to fetch and its `failure` is purely the byproduct of the guard/scope red). So an aggregate red is never an independent defect: enumerate `steps[]` on the jobs that actually ran, attribute each red to its failing STEP, and when guard + scope + verdict all red each tracing to the same `make check-pr-acceptance`, they are ONE red reported three times, not three defects. `gh run view <run> --json jobs` also returns `id: null` (with `conclusion: skipped`) for every fail-fast sibling that never started — those jobs cannot be addressed by an id, so read the RED job's own error with `gh run view <run> --log-failed` (prints only the failed step), never by drilling a skipped job.

### Never report "all gates green" when the acceptance self-red is the only red
A run whose guard step is `failure` must not be described as "all gates green" — a reviewer will read the same run and catch it. The honest, accurate form names both halves at the head: "every actionable gate green at `<head>` (check-pr-closing + openspec-change SUCCESS); the surviving red is the designed #1792 acceptance self-red (unticked criteria), clearing only via reviewer `--proven` (#1644)." Say 'ready for review, BLOCKED on the designed acceptance hold'; do not say 'all green'. If you already posted an overclaim, post a short correction comment naming the passing steps and the designed hold rather than silently leaving it.

### A commit SUBJECT that names an issue `(issue #N)` is a CLAIM — the joined squash text must carry an adjacent `closes #N`

`check-pr-closing` (§143) requires the body's close set to EQUAL the squash text's close set. A
commit message whose SUBJECT reads `type(scope): … (issue #N)` marks a CLAIM but carries NO
`closes #N`, so the joined squash text closes NOTHING while the body `closes #N` — and the gate
reds `squash-mismatch` even though a human reads the subject as closing the issue. Fix the COMMIT,
not the body: amend the message so the joined text carries `closes #N` adjacently (append the close
line to the commit body, or write the subject as `… (closes #N)`), verify `git diff <base> HEAD` is
unchanged (content-lossless), re-run `check_pr_closing.py check` at the new head (rc=0), then
`git push --force-with-lease`. A body-only edit cannot clear it — the squash source is the commit
message.

## Squashing a PR branch to one commit (owner-directed history rewrite), content-lossless

When the owner says "squash the commits and force push": the history rewrite changes commit COUNT, never the tree. Prove it before pushing.
- Capture the pre-squash facts: `git diff --name-only <base> HEAD` and `git diff --stat <base> HEAD | tail -1` (the exact file set + insert/delete totals), and confirm `git status --short` is empty.
- `git reset --soft <base>` (the PR's base, not the moving main tip unless the branch is cut from it), then ONE `git commit` reusing the original message — the message body must still carry `closes #N` (the squash text feeds `check-pr-closing` §143).
- Verify losslessness: `git diff --name-only <base> HEAD` and `git diff --stat <base> HEAD` are IDENTICAL to the pre-squash capture; `git status --short` still empty. A differing count is a bug — stop.
- Re-run the gates at the NEW head before pushing: a squash rewrites every sha, so `check-pr-closing` §143 `commit_closed != body_closed` must be re-verified (body close pair == the single commit's closes) and `check-pr-acceptance` re-measured. Then `git push --force-with-lease` (fetch immediately before; `--force-if-includes`).
- After a force-push, update the PR body: head sha line, and the literal `make bot-preflight` `AGENTS:`/`BASE:` lines re-generated at the current base (flush-left, unindented) — the body's cited head sha is now stale otherwise.
- Force-pushing over an in-flight CI verdict is acceptable ONLY when the verdict cell runs on its OWN concurrency group pinned to its own sha (so it is not cancelled and keeps its verdict); confirm the cell's concurrency group before pushing, and never force-push purely to cancel a run.

## Appending a status note to an issue body WITHOUT perturbing the acceptance parse

The `check-pr-acceptance` gate re-reads the LIVE issue body (`## Acceptance criteria`) at run time, so any edit to an issue body can change the gate's verdict. When appending a status note to a closed-issue's body (squash landed, items met on-branch), keep the `- [ ]` acceptance rows text untouched and re-assert the item COUNT after the edit:
```
gh api repos/<o>/<r>/issues/<n> --jq '.body' | grep -c '^- \[ \]'
# must equal the count before the append (e.g. 3 for one issue, 5 for another)
```
A changed count means the appended markdown swallowed or duplicated an acceptance row and the gate's verdict shifted. Per #1792 never self-tick a criterion (write-back is reviewer-`--proven`-gated, #1644) and never mark a genuine criterion `## Not covered` to deflect the red — append the note under a `> **Status:**` blockquote AFTER the acceptance section, leaving the checkboxes exactly as they were.

## Run every gh/API call through the TERMINAL tool, never execute_code subprocess or bare curl

`gh` resolves on the mise shim PATH (`~/.local/share/mise/shims/gh`) and picks up its auth ONLY in the terminal tool's login environment. A `subprocess.run(['gh', ...])` from the execute_code kernel fails with `FileNotFoundError: 'gh'`, and a token-less `curl` to the GitHub API returns `401 Bad credentials` (the kernel process has no `GH_TOKEN`). Consequence: POSTing a comment, editing a body, or reading a run from execute_code silently no-ops or 401s while appearing to "work". Do all gh/API work with the terminal tool; when you need to parse JSON, run `gh ... --json ... > /tmp/x.json` in the terminal and read the file.

**Post a file body with `-F body=@/tmp/file.md` (capital `-F` reads the file) or `-f body="$(cat /tmp/file.md)"` — a lowercase `-f body=@/tmp/file.md` posts the LITERAL string `@/tmp/file.md`, not the file's content**, so the comment/body lands as a ~15-byte path marker that no reviewer's evidence check accepts while the API returns a happy `id`. Read the posted comment back (`.body` length / contains the expected text) to prove the real text landed.

## A green verdict is scoped to the merge-base — re-check it before claiming green; MERGED is not "needs work"

- **A red `linux / unit` job is not necessarily a broken TEST — `ci-unit` also runs the PR gates, `check-pr-base` among them.** When `origin/main` advances mid-run, the unit leg reds on `[check-pr-base] FAILED: HEAD is NOT cut from origin/main … foreign commits (N)`, and lists YOUR OWN `closes #N` commits as "foreign". Open the unit job's OWN log (`gh api repos/<o>/<r>/actions/jobs/<id>/logs`) and grep `\[check-pr-` before touching any test: if the failing step is `check-pr-base`/`ci-unit`, it is base drift, not a regression — rebase onto the fresh `origin/main` tip (or hand to the rebase lane) and never "fix a test" that did not fail. Distinguish by the `make[1]: *** [Makefile:… check-pr-base] Error 1` + `make: *** [Makefile:… ci-unit] Error 2` tail.
- **`gh pr checks` can show the `guard` gate `SUCCESS` while the RUN `conclusion=failure` — reconcile by reading `jobs[]`.** The guard job passes and the red is contained in a different job (e.g. `linux / unit`); the run-level `conclusion` is the union. `gh run view <run> --json jobs --jq '.jobs[]|.name+": "+.status+"/"+(.conclusion//"-")'` names the actual failing job before you diagnose; do not read the top-level conclusion as "the gate failed".

- A `completed/success` CI run at head X is GREEN FOR THE BASE IT RAN AGAINST. If `origin/main` advances AFTER that run, the same branch becomes `check-pr-base` red and the cited green is STALE — re-fetch `origin/main` and compare `git merge-base HEAD refs/remotes/origin/main` to the live tip before you tell anyone the PR is green/mergeable. A slightly-behind-but-mergeable branch is not broken (rebase only when `CONFLICTING` or base-merges, #1015), but do NOT quote an old run as current truth.
- When the owner has already merged the PR, `state=MERGED` with `mergeable`/`mergeStateStatus = UNKNOWN` is NORMAL, not a defect — those fields are meaningless post-merge. The verification is then the repo truth: issue `state: closed` (closed by the adjacent `closes #N` body line) AND your squash commit present on `git log refs/remotes/origin/main`. A completion guard that keeps signalling "verification not passed" after `state=MERGED` is stale; the merged squash + closed issue IS the verification. Do not re-run CI on a merged PR.
