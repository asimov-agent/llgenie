# Report integrity: your own report is a claim too

A pass report is the fleet's board of record. The next reader — a lane, the owner, or the next tick —
acts on what it says, so an id that 404s is not a typo, it is damage.

## 1. Every id carries pasted output from the same session

Before publishing, for each issue, PR, comment id, run id, kanban task and sha you intend to cite, run the
read and paste the literal output beside it in the report:

```bash
gh issue view <n> --json state,closedAt,title      # closes/creates
gh api repos/<owner>/<repo>/issues/comments/<id>   # a comment you claim to have posted
gh run view <id> --json status,conclusion,headSha  # a run you claim is green
hermes kanban list | grep <task-id>                # a task you claim exists
 git ls-remote origin | grep <sha>                 # "main moved to X"
```

If a claim cannot be read back, report it as NOT DONE with the error text. Never narrate a dispatch,
close, or comment the API does not show — a plausible narrative is indistinguishable from a fabricated one
until someone re-fetches it. And a claim that DID land but was read back badly must be corrected to landed,
not left as "failed to post": a false negative misleads the next reader into re-posting.

### A POST is not idempotent — never retry the POST itself; retry the READ

When a post "cannot be confirmed", the temptation is to re-issue `gh issue comment` / the REST POST. That
manufactures duplicates: one guard-driven pass re-posted the same verdict six times, all six landed, and the
ledger then recorded "board post failed to land" — both halves wrong. `gh issue comment` returns the new
comment URL on success; keep that id and verify with the read path, never by posting again:

- Post ONCE. Capture the returned `#issuecomment-<id>` (or the REST `id`).
- If the readback looks empty ("0 new comments", a stale slice), switch the READ tool/path once — a
  different filter, `--paginate`, or the by-id endpoint — before concluding anything. A `cd: <stale-dir>`
  error or a cached `.[-1]` in the read command is a read artifact, not evidence the post failed.
- Only a by-id read that 404s is proof of non-landing; then re-post once and say so.
- Correcting a ledger entry that said "not landed" must state the true result (id + time + count) rather
  than deleting the history — a wrong entry left uncorrected makes the whole record untrustworthy.

### Read a comment back by its OWN id, never from a "newest" slice of the list

`repos/<o>/<r>/issues/<n>/comments` returns comments in **ascending creation order**. A read-back built as
`... | jq '.[0]'` (or any naive slice) therefore returns the OLDEST comment and you will "verify" a comment
that is not the one you posted — or conclude yours never landed. Both happened in one pass.

The only read-back that is proof: fetch the comment you created by the id the POST returned.

```bash
gh issue comment <n> --body-file /tmp/body.md      # prints ...#issuecomment-<id>
gh api repos/<o>/<r>/issues/comments/<id> --jq '{id,at:.created_at,who:.user.login,head:(.body[0:60])}'
```

If you want the newest comment in a list anyway, sort explicitly (`sort_by(.id) | reverse | .[0]`) — never
trust the API's order or `.[-1]` on a payload you have not checked. Note that a comment id returned by the
POST is an *issue* comment: `repos/<o>/<r>/issues/comments/<id>`, not `.../pulls/comments/<id>`; the wrong
path 404s and reads like a phantom comment.

## 2. A cron-generated report can confabulate a whole board

A scheduled tick that runs under context compression can lose its grounding and emit a complete, coherent,
entirely fictional pass: new issue numbers in a block, comment ids, kanban task ids, invented main shas, and a
close that never happened. Signature: the claims are *internally* consistent and *externally* all 404.

- Spot-check two or three of the strongest claims before relaying anything: `gh issue view <claimed-new-id>`,
  `gh api .../issues/comments/<claimed-id>`, `git ls-remote origin | grep <claimed-sha>`.
- File the incident durably as an issue (the report may have been relayed to the owner already) and harden the
  *generating prompt*, not the terse report: add the pasted-output rule above to the cron job's prompt, back the
  config up first, and verify the edit by re-reading the file.
- A tick report that is *internally* consistent but *behind* reality is a different failure: **stale-by-time**, not
  fabricated. It quotes `main=<sha>`, an open-PR list, and "which lanes are idle" as measured at the moment it ran;
  in a fast fleet the board moves under it, so by the time you read it main has advanced and PRs it lists as open
  have merged. Never relay a tick's sha or PR census as current — re-fetch `git rev-parse origin/main`, the open-PR
  list, and the merged-state of each PR it names, and report the corrected board (name which claims were stale and
  by how much). Its *dispatch decisions* can still be sound forward work even when its census is wrong; keep those,
  correct the board. Distinguish the two modes explicitly in your report: "tick confabulated" vs "tick ran before N
  merges landed".
- Repeated "Context compression is already running for this session" delivery failures plus the kanban
  dispatcher reporting memory pressure identify a host constraint, not lane refusal. Report it owner-gated; do
  not dispatch harder into it. Delivery-result semantics (queued / failed / queue_full):
  `references/stalled-lane-and-dispatch-delivery.md`.

## 3. A tool call that "ran" may have aborted atomically — and one that printed nothing may have succeeded

Both directions are the same rule: the exit status and the output are not the fact; the remote state is.

`gh issue create ... --label <label-that-does-not-exist>` fails the WHOLE call — no issue is created — and prints
only the label error. Piping through `tail -1` hides everything except that line, which reads like success.

- After any create, verify by re-fetching: `gh issue list --search "<distinctive title words> in:title"` and
  paste the number. Exit status is not the fact.
- Check the label vocabulary first (`gh label list`); this repo's labels are `agent:implement`, `agent:ready`,
  `agent:refined`, `bug`, `severity:*` — an invented label (`agent:triage`) silently voids the create.
- If a prompt or doc is being hardened to cite an issue number, FILE the issue first and patch the real number in.
  A citation is itself an id and must survive `gh issue view`; writing the number before it exists recreates the
  exact defect the hardening is meant to prevent.

**Silent success is the dangerous mirror.** A host lane whose shell returns `rc 0` with *no stdout* often
concludes its `git push` / `gh pr create` "did not take" and re-runs it — manufacturing a duplicate branch
push or a second PR for an issue that already has a vehicle. The command frequently *did* land; the terminal
just swallowed its output. Before anyone re-runs a push or a create, prove what already exists on the remote:

```bash
git ls-remote origin refs/heads/<branch>     # branch present at the head the lane meant to push?
gh pr list --head <branch> --json number,state,headRefOid
```

If the branch and PR already exist at the expected head, the correct instruction to the lane is **do not
re-push, do not open a second PR — your work landed, update the existing vehicle**. A re-push after silent
success is how one issue accrues two vehicles (the "one vehicle per issue" rule). Verify before re-running;
never read empty output as failure.

## 4. Count findings, not mentions

`grep <lane-name> | wc -l` counts explanatory lines, tree-ahead notes and headers as findings — a lane reading
"4 hits" may have zero FAIL lines. Attribute per lane from the FAIL lines only:

```bash
python3 scripts/check_agent_profiles.py check 2>&1 | grep -E "FAIL" \
  | awk '{for (i=1;i<=NF;i++) if ($i ~ /^llgenie-/) {c[$i]++; break}} END{for (l in c) print l, c[l]}'
```

Run the gate on the freshly fetched `origin/main` sha and name that sha in the report; a lane total is a claim
about a tree, not about the repo.

## 5. Re-measure before publishing, in either direction

In a fast fleet an id that 404'd ten minutes ago can exist now — often for an unrelated reason, with a different
title. Before writing "does not exist" or "exists", re-fetch in the same breath as the report; and when a
number turns up that you previously proved phantom, say which one it is and what its title is, rather than
quietly reusing the number.

### Write the measured figure into the body at POST time — a body written before a re-measure carries the stale one

A finding body drafted, re-measured, then posted from the file written *before* the re-measure publishes the OLD
figure with no trace it was superseded. Pattern: draft says "N total", you re-measure to a different N, refine
in chat, but the POST reads the pre-refine file — the stale number and any garbled line in it go live on the
board. Rule: the moment a count/list/number is re-measured, **rewrite the body file in that same step, then
post from the rewritten file** — never post from a path last written before the correction. After any post that
carried a figure, read it back by id and assert the EXACT number is present; if a stale figure landed, post a
correction on the same thread naming the true figure and which line was wrong (a correction that lives only in
a DM or your ledger does not exist for the next reader), then record that you own the error.

### Readback assertions must be case- and markdown-tolerant

A literal phrase test fails on legitimate markdown content (`does **not** exist`, `not MET` vs `NOT MET`,
en-dashes) and reads as "the post is wrong" when the post is correct. Use `test("<phrase>";"i")` and match
words, not punctuation. Full rule and examples: `references/stalled-lane-and-dispatch-delivery.md`
("Body-content assertions must be case-insensitive AND markdown-tolerant").

When a marker assertion comes back `false`, **dump the raw body before concluding the post is wrong**:
`gh api repos/<o>/<r>/issues/comments/<id> --jq .body`. Match the phrase you actually wrote, not a paraphrase —
`test("bare 53")` fails against a body saying `bare: 53`, and `test("ancestor of main")` fails against
`ancestor of origin/main`. A punctuation-only false negative here is what drives the duplicate re-post the
section above forbids: fix the assertion, never re-POST.
