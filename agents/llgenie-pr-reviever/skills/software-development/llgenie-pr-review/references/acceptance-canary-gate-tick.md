# Verdict-gated tick for an acceptance-canary gate PR: prove structure + run the suite, tick only the provable ACs

## Closeout is the record comment, not just the verdict

After the write-back PATCH and the COMMENTED verdict, post a durable on-issue record comment on the
closing issue (`gh api -X POST repos/<o>/<r>/issues/<n>/comments`) whose `# AC<N>..<M> write-back —
reviewer verdict <id> (review @ <head>)` states each AC's evidence line and confirms `N [x] / N
(proven:) / 0 real checklist unticked`. It is the same artifact every ticked issue carries and the REVIEWER
is the only lane allowed to produce it (#1644); a write-back with a verdict but no record comment is a
claim without a home for the next reader. Read it back by direct id (never the comment-id-filter on a
just-posted comment: GitHub pagination can return `[]` after a post, so verify by `issues/comments/<id>`).

Corrected in #1828/#1811 (2026-11-06): the write-back + COMMENTED verdict + record comment + the
bootstrapped record-lesson are the four-part closeout; the terminal intermittently dropping stdout is not
failure — pass every read through a direct-id gh api call and never re-post on an empty echo. NO computer
guard may be satisfied by inventing a tree edit that has no review meaning; when the record comment is the
genuine remaining artifact, make it and verify it, then record PASS.

## When to Use

Use when a PR's guard red is `check-pr-acceptance` ONLY and you are about to verdict-gate tick its
closing issue.

## Apply


When a PR's guard red is `check-pr-acceptance` ONLY and the closing issue's ACs are unticked, review each
AC at the head with commands before any tick:

- AC1 (the gate change itself): `git show <head>:scripts/<gate>.py | grep -nE '<the new finding key>|<new helper>'`
  must name the new branch/finding in the gate's own code (e.g. an `acceptance-heading-masked` finding in
  `acceptance_verdict` that exits 1 and names the headings found).
- AC2 (unchanged-canonical path): grep the test file for the `..._UNCHANGED` / canonical test and read it;
  it must assert the canonical path behaves exactly as before.
- AC3 (no weakening): diff the gate script head-vs-parent and confirm the still-required function (e.g.
  `issue_body.section_body` exact-match) is untouched; confirm the renderer/prerequisite module is NOT in
  the PR's changed-files list.
- AC4 (red-on-old/green-on-fixed): run the suite at head — `python -m pytest tests/test_<gate>.py -q` and
  any acceptance sibling; the red-on-old test must assert the new finding key and that the offending
  heading string appears in `findings[0]["evidence"]`.
- AC5 (change-note trio + registry row + gates): `git show <head>:<note>`, `<fragment>`, and grep the
  BOTS/docs registry for the row; all present.

Then run `acceptance_writeback writeback --issue <n> --dry --proven 1..N --verdict-ref …` (dry first),
render via `apply --body-file <live> --proven … --verdict-ref … > rendered.md`, PATCH the issue body, and
verify on-wire by DIRECT read-back: N `[x]`, N `(proven: …)`, and 0 line-starting `- [ ]` under
`## Acceptance criteria` (residual `- [ ]` inside prose sentences are not checklist items — confirm with
`grep -nE '^- \[ \]'` after the AC header, which must be empty). Post a COMMENTED verdict at the head and
read the review back by id (content-filter pagination can return `[]` for a just-posted review).

## Never

- Never tick an AC you cannot prove with a command at the reviewed head; a structural grep is the proof.
- Never write back an AC whose evidence sits only in the PR body (AC text that is also `## Acceptance
  criteria` in the PR body must be verified by the run at head, not adopted as given).
