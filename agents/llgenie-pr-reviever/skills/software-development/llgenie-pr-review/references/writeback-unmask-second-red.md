# Write-back unmask may surface a SECOND red — read every failure leg

Clearing the acceptance self-red (verdict-gated write-back, #1644) and re-running the
workflows does not end the review. The rerun can surface reds the hold had hidden —
sometimes BEYOND the predicted base-drift unmask (rebase-lane recut, #845/#1015).

## The unmask chain, in order

A verdict-gated write-back rerun at the same head typically peels in this order:

1. `check-pr-acceptance` flips SUCCESS (the pin you just wrote).
2. `check-pr-base` unmasks the base-drift (rebase-lane recut; the PR's parent is no longer
   the base). Expected and routed — not a defect in the PR.
3. ci-scope/`make` gates may then reveal a red the acceptance hold had hidden: a structural
   validator failing on the PR's OWN added change (spec delta missing `## ADDED Requirements`
   / `#### Scenario:` blocks and correctly NOT waving itself through with `skip_specs: true`).
   A first-look reading that reports the scope red as "same acceptance self-red" is WRONG:
   two distinct reds, two different owners.

## Discipline

0. `skip_specs: true` (or any validator skip) added to silence a failing structural gate is a
   defect, not a fix — report it as one. The delta contract exists so prose-only specs cannot
   pass; a gate you switched off proves nothing about the change it was guarding.
1. After ANY write-back rerun, list EVERY `conclusion==failure` job's failing steps in
   BOTH the guard and the scoping workflow; never collapse multiple failures into one
   known class.
2. Reproduce an unfamiliar red with the CI's own image locally (for openspec:
   `docker run -v $PWD:/repo -w /repo ghcr.io/asimov-agent/llgenie/openspec:<tag>
   openspec validate <change> --type change`) before attributing it.
3. Post the finding on the PR (comment id), route to the owning lane
   (@llgenie-ci-pipelines-maintainer for workflow/openspec structure), and record the
   result in the final gate-state comment. The ticked ACs and the verdict STAND — the
   PR simply is not mergeable until the unmasked red is fixed by its lane.
4. Never claim "only the one red" after a rerun; state the full table of green/red
   gates at the head.
5. Follow through when the owning lane pushes the fix: the head moves. Verify the fix at the
   NEW head with the same validator (quote totals), then **re-anchor** the pins and verdict —
   not re-judge — when the graded files are byte-identical across the move (see
   `verdict-sha-anchoring.md` → "Re-anchor vs re-judge"). A finding you posted and never
   closed on-wire leaves the board unable to tell fixed from abandoned.
6. A fix that converts "silently absent" into "accounted-as-skipped" can still leave the very
   seam the issue's AC names red. When a regression fix relabels an out-of-band-but-fitting model
   from dropped to `skipped`-with-reason, grep the seam FILE the AC names for `assert "…resolve…" in <stdout>`
   (an `offer()`-asserting smoke test like `test_pick_matrix_arch_perms.py`). Measured #2049:
   `qwen2.5-0.5b` (2GB tier, 24 GB host) — pre-#1969 `74 passed` (OFFERED), main `cb6c56a9` AND head
   `e1ec9d9` BOTH `7 failed` (silent-drop→skip relabelled, same failures); the diff never touched the
   arch_perms file. The hermetic regression (AC3) passed and was ticked with a reproducible command,
   but AC2 naming the arch_perms seam stayed red: a skip is not a green when the seam asserts offer.
   Three-baseline evidence (pre-break → main → head, same container) proves the seam was not restored.
   Tick only the delivered subset; post the seam-red with file:line + the three-baseline table; the
   fix must offer the model or the seam must change — "skipped" is not AC2-satisfying for an
   offer-asserting test.
