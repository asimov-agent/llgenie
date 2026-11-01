# Fold residual reference into the tree (#1352)

`agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md:574` names
`references/fold-residual-and-corrections.md`, which was live-only (absent from the
tree) — a dangling reference that `test_agent_profiles` caught (`skill-reference-missing`)
and that reds the `linux/unit` leg of every PR on `main`, including #1092's verdict
(run 41311218548).

The file records fold-residual discipline (measure before claiming closure, answer
cross-timed corrections once, close-wiring in the PR body). It is real lane guidance,
committed byte-identical to the live profile (2,426 B, sha256 `d563683b`).

The tree SKILL body is unchanged (`86bb8ccd`, == `main`); the fold lands only the missing
reference. The two remaining `absent-from-tree` findings are the merge-conflict lane's
live-only `llgenie-pr-rebase` skill dir (out of this issue's scope; fires only where that
host profile exists).
