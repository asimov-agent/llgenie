# Bind to a cited comment's BODY, not to its id or its existence

A lane relaying another lane's proof often hands you a comment id ("evidence is in comment 6716136014").
An id that resolves is **not** evidence: the comment can be a stub. Measured case — a cited evidence
comment fetched to `{"body": "@-", "body_len": 2}` while the message claimed a full pytest output
(`12445 passed, 128 deselected in 1409.48s`). The number was never on the PR.

## Rule
1. `gh api repos/<r>/issues/comments/<id> --jq '{id,user:.user.login,body_len:(.body|length),body}'`
   and read `body_len` / the body. A 2-character body is not a proof, whatever the message says.
2. Judge the acceptance criterion from YOUR OWN measurement at the head, never from a relayed claim
   and never from an id that merely exists.
3. When the cited comment is empty, say so plainly in the verdict/status comment — quote the body
   (`"@-"`) and its length — so a future reader does not treat an empty comment as the evidence. Use
   it to supplement, never to block: if you measured the same thing yourself, the criterion stands on
   your run.
4. Cross-check arithmetic when the relayed number differs from yours: a filtered run (`-m network`)
   `12445 passed, 128 deselected` and an unfiltered `12573 passed` are the same set and corroborate
   rather than conflict. State the reconciliation.

## Companion: a re-run that reds a DIFFERENT gate is not the same failure
After a write-back clears `check-pr-acceptance`, the same CI run's `linux/unit` can fail at
`check-pr-base` because `main` advanced past the PR's base. If the PR base is still an **ancestor** of
main, it is merely-stale-but-clean (issue #2016/#845 class), not a foreign-branch defect — the remedy
is a rebase by the rebase lane (#1015), and the acceptance verdict stands once the graded files are
byte-identical. Name it as a different gate; do not report it as the acceptance failure returning.
