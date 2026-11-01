# Round-14 fold: classify-reds rule (#1356)

`agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md` carries a +231 B live-ahead delta:
the "classify whole-suite reds as inherited-main vs fold-regression" rule, pointing at
`references/classifying-suite-reds.md` — a live-only reference absent from the tree (the
round-14 residual measured on #1352 / after round-13 #1339).

This fold lands both live→tree byte-identical at branch time (SKILL `0bc09907`, 100,442 B;
`classifying-suite-reds.md` 2,397 B, sha256 `a4052d84`). Base `origin/main@3b8d439e`.

The SKILL body stays at the ~100k size convention — the new rule's prose lives in the
reference file it points at, not in the SKILL body.
