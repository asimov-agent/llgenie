# PR body closing keywords and `closingIssuesReferences`

GitHub's issue-linking parser scans the PR **body and title** for a closing keyword
(`close`, `closes`, `closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves`, `resolved`)
followed by an issue reference. Any `#N` that sits on a line with such a keyword — even
inside a negation like "this does **not** close #1245" — is added to
`closingIssuesReferences` and **that issue is closed automatically when the PR merges**.

## Why it bites this lane

When folding a lane's change under an umbrella issue, the body naturally wants to say
"this is one lane's fold of the umbrella; it does not close the umbrella." The literal
string `close #<umbrella>` there is what the parser reads — the `not` is invisible to it.
The PR then carries two close targets, and an owner merge silently closes the umbrella.

## Rule

- Reference an umbrella issue WITHOUT the token adjacent to a closing keyword. Use
  "the umbrella contract (issue 1245), which stays open" — drop the `#` or keep the
  number far from the keyword — rather than "does not close #1245".
- The only `#N` that should follow a closing keyword is the one the PR really closes.
- Keep each `Closes #N` on its own line, one target.

## The forced `closes #N` can auto-close a MULTI-LANE umbrella on merge

`check-pr-closing` demands one adjacent `closes #N`. When the dispatched work is tracked on a FLEET
UMBRELLA issue whose own AC requires every lane to land, and no smaller per-vehicle issue exists to close
instead, that `closes #umbrella` auto-closes the umbrella `completed` on YOUR merge — before the other
lanes' vehicles land. You cannot dodge it by omitting the keyword: the gate reds.

- Prefer closing a specific vehicle/sub-issue if one exists; keep the umbrella reference NON-adjacent (see
  the opening rule) so only the vehicle closes.
- If the ONLY legitimate target is the umbrella, merge as the gate requires, then FLAG the premature
  umbrella-close to the planner — re-opening is the planner's board call, never a lane self-reopen — naming
  the still-open sibling vehicles and that the "all lanes" AC is unmet. Record it on the issue so the board
  shows the umbrella as reopen-until-landed, not silently done. This is a board-reconciliation note, not a
  red, and it does not change what you merge.

## `check-pr-closing` wants the body close-SET to EQUAL the squash close-set

Beyond GitHub's auto-close, the repo's own `check-pr-closing` gate (in `ci.yml`'s `scope` job) compares
the PR body's parsed close-set against the JOINED commit messages' close-set and reds with
`N violation(s)` when the two DIFFER in either direction. So a body that closes the right issue but ALSO
carries an unrelated close — e.g. an issue-template line reading "fix #1646" while the commit closes
`#1657` — parses as `{1646, 1657}` vs `{1657}` and fails, even though `closes #1657` appears in both.

- Strip every closing keyword from prose that references another issue. `"blocked by #1646"` /
  `"unblocks #1655"` are safe (no keyword adjacent); `"fix #1646"` / `"does not close #1646"` are NOT —
  the keyword adjacency is all the parser reads.
- Leave exactly one adjacent `closes #N`, and make the commit/squash message close that same single issue.
- Verify both sets agree before pushing:
  ```sh
  gh pr view <n> --json body --jq .body | grep -oiE '(close[sd]?|fix(e[sd])?|resolve[sd]?) +#[0-9]+'
  git log --format=%B origin/main..HEAD | grep -oiE '(close[sd]?|fix(e[sd])?|resolve[sd]?) +#[0-9]+'
  ```
  Both lines must list the SAME single number.

## A MERGED PR's body is still editable — correct a wrong anchor on it

Merging freezes the code, not the body. `gh pr edit <n> --body-file <file>` succeeds on a merged PR,
so when a PR is found to claim `closes #<wrong>` (e.g. an issue already closed as a ghost) the correct
record fix is a body edit to the right anchor, plus a sentence saying this PR does NOT close the old
one. Do not report "the body is frozen / cannot be retitled" and downgrade to a comment — that was the
error; the edit is available. After editing, read the change back as evidence: a **term count**, not the
exit code — `gh pr view <n> --json body --jq .body | grep -c 'closes #<right>'` = 1 and
`... | grep -c 'closes #<wrong>'` = 0. Confirm the new target is a live issue and that
`closingIssuesReferences` names it (the read-back after the edit is the fact, per the rule below).

## A bot PR's body carries TWO gate-checked lines: `closes #N` AND the `AGENTS:`/`BASE:` pair

Two preflight gates read the LIVE PR body and red independently — fix both in one `gh pr edit`:

1. **`make check-pr-closing`** — `Issue: #N` in the body is prose, not a close: GitHub's parser and the
   gate both want a keyword (`closes`/`fixes`/`resolves`) adjacent to `#N`. Put `closes #N` on its own
   first line; then `closingIssuesReferences` is non-empty. Measured: a body whose only reference was
   `Issue: #1704` read `closingIssuesReferences: []`, and the lane's own message claiming "it closes
   #1704" did not make it so.
2. **`make check-pr-agents-line`** — the body must carry `AGENTS: <main-sha> <bytes>b <lines>l` (byte and
   line counts of `AGENTS.md` **at upstream/main**, not at your head) plus a SEPARATE
   `BASE: <main-sha> (== origin/main at open)` line. Never hand-invent this shape — the counts are
   measured:
   ```sh
   git show <main-sha>:AGENTS.md | wc -c   # bytes, e.g. 91766
   git show <main-sha>:AGENTS.md | wc -l   # lines, e.g. 1363
   ```
   A hand-typed line like `AGENTS: ci-pipelines lane; scripts/ + tests/ only; Base: 9ca3a5f4` reds the
   gate — the guard script (`scripts/bot_preflight.py::agents_line`) formats it as
   `f"AGENTS: {main} {agents_bytes}b {agents_lines}l"`, so reproduce that exactly. The canonical shape is
   visible on any merged bot PR (`gh pr view <merged> --json body --jq .body | grep -E '^AGENTS|^BASE'`).

   **Nothing may follow the `<bytes>b <lines>l` counts on the `AGENTS:` line — the gate regex is
   `^AGENTS:\s+([0-9a-f]{7,40})\s+(\d+)b\s+(\d+)l\s*$`, anchored with `\s*$`.** A natural-looking
   annotation appended for a human reader — `AGENTS: <sha> 91766b 1363l (=~ origin/main at open)` or
   `… 1363l (measured at open)` — reds `check-pr-agents-line`; the runner's own `BASE:` line already
   carries the `(== origin/main at open)` note, so keep the parenthetical there and leave the `AGENTS:`
   line bare. **The symptom misleads: the guard log reads `[check-pr-hygiene] PR body: no AGENTS line`
   even though a correct-looking line IS present** — do not conclude the line is missing or that
   `check-pr-closing` is at fault; read the line's exact tail and strip anything after the trailing `l`.
   Run the gate itself on the host to confirm the fix before re-pushing (`agents-line` returns rc=0 and
   `[check-pr-hygiene] OK: the AGENTS: line is reachable from both head and base`).

   **A malformed SHA defeats the regex as silently as a missing line. The `[0-9a-f]{7,40}` group caps at
   40 hex chars: a 41-char sha, or a hex block with a transposed/extra character that makes the whole
   `[0-9a-f]+ 91766b` run no longer match `\s+(\d+)b`, returns `no AGENTS line` from a line that looks
   right.** Before blaming the missing line / trailing annotation, verify the sha itself: the gate's group
   is genuine 40-lowercase-hex `[0-9a-f]{7,40}` and it must be the REAL `upstream/main` tip sha (from
   `git rev-parse upstream/main`), never a hand-edited `fd87042a…` from an earlier message. Measure the
   cite as `len(sha)==40` and test the regex against the exact body line (`re.search(AGENTS_LINE, body)` is
   the gate's own check) so a silent cap failure is caught on the host, not on the wire. (Measured #1810:
   a 41-char `fd87042a6b10095…58e2` sha that was NOT the base made the gate decline a visually-correct
   line until the body was re-edited with the real 40-char `b6869f7b…` tip.)

## Every body-reading gate now reads the LIVE body — but verify it, and know the snapshot shape if you find one

`check-pr-closing` runs in more than one workflow. It USED to be split: `ci.yml`'s `scope`/`guard` jobs read
the body LIVE via `gh api .../pulls/<n> --jq .body`, while the reusable `pipeline.yml` `linux` job (which
`ci-unit` reuses) fed the gate from `PR_BODY: ${{ github.event.pull_request.body || '' }}` — the **frozen
event snapshot captured when the RUN was created**, so a body-only edit was invisible and every `gh run
rerun` re-read stale bytes. That asymmetry produced the tell: guard jobs green (live) while `linux / unit`
stayed red on the same corrected body.

**That snapshot form is fixed in `pipeline.yml` — the unit job's step now reads live**, in the same shape as
scope/ci.yml:

```yaml
run: |
  PR_BODY=$(gh api "repos/$PR_REPO/pulls/$PR_NUMBER" --jq '.body // ""')
```

Consequences worth holding:

- **A body-only fix no longer owes a new head** for the unit job. Edit the body, and the next run (a rerun or
the next push of any change) reads the current body. Do not push an empty commit to "refresh the snapshot" —
that workaround is obsolete and adds a run for nothing.
- **Rule if you DO meet a step still on the event snapshot** (a workflow the fix has not touched): to clear a
gate whose job reads `github.event.pull_request.body`, you must create a NEW `pull_request` event — push a new
(amended or empty) head — not edit the body and not rerun the job. Verify by the new head's own check-runs,
not by the rerun.
- **Pin the behaviour with an anti-drift test, and assert the NEGATIVE too.** The test should assert the
`gh api repos/$PR_REPO/pulls/$PR_NUMBER` read is present AND the `github.event.pull_request.body` string is
absent from the step's `run:` block — a test that only checks the live read passes on a step that still
carries a stale snapshot alongside it. Prove it by planting the snapshot form back and watching the test
RED, then restoring.

## Verify (always, after any body/title edit that touches issue refs)

```sh
gh pr view <n> --repo asimov-agent/llgenie --json closingIssuesReferences \
  --jq '.closingIssuesReferences[].number'
```

**jq has NO `grep` function** — `--jq '...|grep("^AGENTS")'` fails `function not defined: grep/1`. To
pull a body line back, split and select in jq itself:
```sh
gh pr view <n> --json body --jq '.body|split("\n")|map(select(startswith("AGENTS:")))|.[0]'
```

Assert the output is EXACTLY the set you intend (subset check against the intended set).
If an unintended number appears, edit the body to remove the keyword+ref adjacency and
re-read — a body edit re-evaluates the set, so the read-back after the edit is the fact,
not the pre-edit state.
