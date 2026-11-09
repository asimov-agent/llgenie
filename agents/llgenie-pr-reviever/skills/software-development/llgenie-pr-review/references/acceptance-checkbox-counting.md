# Count acceptance checkboxes section-scoped, never whole-body

Tally `- [x]` / `- [ ]` ONLY between the `## Acceptance criteria` heading and the next `##` heading.

A whole-body `grep -c -- '- \[x\]'` / `- \[ \]` over-counts: the "How we fix it" numbered list and other prose checkboxes are not acceptance criteria, so the section tally and the body tally diverge.

Worked example: #1796 read **3/6** in-section (#2/#4/#6 ticked, #1/#3/#5 open) but **4/10** whole-body — the extra ticks were "How we fix it" numbered items. Reporting the body count as the acceptance tally is a census error a reviewer must not make.

Rule: report the in-section count, and cite the head sha it was measured at. Verify with a section-scoped parse (split on `## Acceptance criteria`, then on the next `##`) before quoting a tally.

## Grep the boxes fixed-string, from a script file

Count with `grep -cF -- '- [x]'` / `grep -cF -- '- [ ]'`. `[x]` is a character class in basic
regex, so it needs escaping; escaping it through a nested quote layer (`'- \['"'"'x\]'"'"'`) yields
`unexpected EOF while looking for matching` and reads like a broken shell rather than a typo. `-F`
makes the pattern literal and drops the quoting problem entirely.

Put the tally (counts + `comment=<id>` + `head=<sha>` occurrences + the box lines themselves) in a
`.sh` file and run the file, not an inline one-liner in the `terminal` call — same hazard as a
Python heredoc, and the file is re-runnable when the head moves.
