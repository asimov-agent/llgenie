# Splitting one red across owners, and proving a filed mutation landed

> Companion: `references/bot-pr-gate-battery.md` — the full local hygiene-gate battery to run before a push, the `check-pr-acceptance` designed hold and its `## Not covered` leading-three-words matching rule, and why a PR's `ci-verdict` red is the pre-existing gate (the verdict workflow checks out `main`, not the PR branch).

## Reading the failure line (before attributing anything)

A red's check colour and rollup are not the cause. Pull the failing job's log to the actual failure line, then grep the tree for where the decision lives.

```
gh api repos/<repo>/actions/jobs/<job_id>/logs            # first try
gh run view <run_id> --log --job=<job_id> | grep -nE 'ERROR|Error|make: \*\*\*'
```

If the logs endpoint returns empty, do not conclude the job has no output — fall back to `gh run view --log --job` and search for the `ERROR`/`make: ***` lines. Quote the quoted line plus its step name in every finding; a finding without the log line is a claim about a badge.

## One red, two root causes, two owners

A single failing cell (or a sweep's acceptance criterion) often straddles two disjoint causes: one in product code (`scripts/*.py`, an engine image, a serve leg) and one in the workflow/gate/make files this lane owns. Do **not** collapse the situation into "fixed" or into "hand it all back".

1. Name the mechanism with `file:line`, not the symptom. "Cache import failed" is a symptom; `_buildx()` reading `CACHE_WRITE = os.environ.get(...) == "1"` and arming `--cache-to` under it, while the job's credential/login step is gated `inputs.push == 'true'`, is the mechanism.
2. **Product half** → hand back to `@llgenie-planner` as a comment **on the issue** (a DM may queue-fail; a comment is the durable record), carrying the log-quoted cause, the `file:line`, and the candidate remedies, stating plainly which remedy belongs to product code and that this lane did not edit it.
3. **Workflow half** (an env set unconditionally while the credential step is gated off, a step that cannot authenticate what it arms) → file it as its own refined issue in the six-section shape. Audit discipline holds: a finding filed this pass is not implemented this pass, and it is not a licence to push a branch you were not dispatched for.
4. Never claim the acceptance criterion green while either half is open. The hand-back names both halves and their owners, and states that the criterion cannot pass until both land (and names any third issue the criterion also depends on).

Tolerance beats tolerance-of-a-red: a missing cache should cost a cold build, not a red cell — but that tolerance lives in product code, so it is a hand-back, not a pipeline edit.

## Proving a mutation landed

A `gh issue create` / `gh issue comment` exit code and its returned URL are **not** the fact. Read back by direct id with boolean content checks, so the check proves the body carries the mechanism rather than that a comment merely exists:

```
gh issue comment <n> --repo <repo> --body-file body.md      # returns the comment URL; take the trailing id
echo "$URL" | grep -oE '[0-9]+$'
gh api repos/<repo>/issues/comments/<id> --jq \
  '{id,author:.user.login,issue:.issue_url,created_at,
    has_mech:(.body|contains("engine_image.py")),
    has_log:(.body|contains("ERROR")),
    has_boundary:(.body|contains("handed back"))}'
gh api repos/<repo>/issues/<n> --jq '{number,state,ac:(.body|contains("## Acceptance criteria"))}'
```

List the thread (`gh api repos/<repo>/issues/<n>/comments --jq '.[]|{id,created_at,head:(.body[0:60])}'`) before posting: a lane may have already attributed or retracted a claim on the same issue, and a later comment that ignores it is a contradiction on the record.

Verify each id by **direct lookup** (`gh api repos/<repo>/issues/comments/<id>`), never by filtering a paginated list with `.[]|select(.id==<n>)` — an integer/string typing mismatch makes the filter match nothing silently, and an empty result reads as "the comment is missing" when it is present.

## A dispatch cites a stale head — measure live before acting

A follow-up dispatch can name a branch/PR at an **old head** (`…red @ <sha>`, an attribution id) for work that has since been amended, rebased, or merged. Never act on the cited sha: it is a claim about a past moment. Re-measure the live object and reconcile against what you find.

```
gh api repos/<repo>/pulls/<n> --jq '{state,merged,merged_at,merge_commit_sha,head:.head.sha}'
```

- If `merged:true`, the instruction to amend/force-push the branch is **void** — amending a merged commit is wrong even when the gate red it described was real. Reconcile on the issue by quoting the merge commit message that shows the close-set already aligned, and stop.
- The gate red a stale dispatch describes (e.g. a squash body that claims `(#N)` without an adjacent `closes #N`) was usually fixed by the amend/rebase that produced the *current* head; confirm it in the merged squash message, not by re-running the amend.
- Post the reconciliation as a comment on the issue (the durable record), then DM the planner — the planner may be reading a stale board, so restate the measured merged sha and merge-time to correct it.

## The commit is the index, not the working tree — verify the committed blob, not the file you see

`git commit` (no `-a`, or after any `git reset --soft`) commits the **index**, which a
`reset --soft` leaves at the OLD tree. Repair the working file, see the correct content on disk,
`git commit` anyway, and you ship the stale version — and it looks clean until review. The tell is
a ` M` line in `git status` AFTER the commit: the tree you fixed is still unstaged while HEAD
carries the broken blob.

- After repairing a file post-reset, **`git add` the file** before `git commit`, then confirm the
  index matches what you fixed: `git show :path | grep -c '<the symbol you added>'`.
- Verify the **committed** blob, never the working tree: `git show HEAD:path > /tmp/c.py` then
  `python3 -c "import ast;ast.parse(open('/tmp/c.py').read())"` (or grep the symbol there). A file
  that compiles on disk but `IndentationError`s from `git show HEAD:` was committed from a stale
  index.
- Run the full suite against the **staged** file (`git add`, then the pinned container run) so the
  thing you measured is the thing you push; re-check `git show HEAD:path | wc -l` and a symbol
  count before the force-push.
- After the push, re-read the file at the PR head — `gh api repos/<o>/<r>/contents/<path>?ref=<head>`
  → parse it — the wire file must be correct, not just the local one. A `git show --stat` of the
  commit showing deletions (`22 deletions`) where you intended a pure add is the same warning: you
  committed a replacement, not an append.

## Never replace a whole function block to "add" a test

Adding a test by patching a whole existing `def test_...(): ...body...` as `old_string` with a
replacement that omits the body silently DELETES that test and leaves a bare `def` header →
`IndentationError` on collection, and the deleted test's coverage vanishes with no failing
signal until collection. Append the new test (`cat >> file <<'EOF'`) or anchor the patch on a small
unique line; afterwards assert BOTH counts hold — the original test still present AND the new one
present (`grep -c 'def test_the_original' && grep -c 'def test_the_new'`) — and that the whole
file parses.

## Completion-reflex discipline

When a progress/completion guard keeps demanding "a required task-relative change", **check the
wire before dismissing it**: `git show HEAD:<path>` (the committed blob) and the PR-head file via
`gh api repos/<o>/<r>/contents/<path>?ref=<head>`. If the mutation is genuinely on the wire and
verified, the reflex is not evidence — quote the record ids and head sha you measured, restate the
state, and stop. But the reflex CAN be materially right: a pushed broken or missing test, or a
commit that captured a stale index, is exactly what it may be pointing at. Verify before you
dismiss, and never fabricate a file edit or open an un-authorised PR to silence it.
