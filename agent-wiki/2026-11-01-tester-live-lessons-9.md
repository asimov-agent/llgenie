# agents(llgenie-tester): round-9 split fold — live→tree (#1079)

## The fold

Round 9 carries the deferred live-ahead residual (planner-logged at `#1312` review): the live
`agent-profile-versioning.md` grew **+1,199 B** after the round-8 fold, and the live `SKILL.md`
advanced past what `#1312` folded. Re-measured at fold time right before copying (the standard);
the fold tool reported **5 same / 2 drifted / 0 live-missing / 0 live-only / 0 mid-write** and copied
both tree files to match live:

| path | live hash (copied) |
| --- | --- |
| `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md` | `d135eba6035f` |
| `agents/llgenie-tester/skills/llgenie-pr-testing/references/agent-profile-versioning.md` | `afaab960e24f` |

## Why this PR exists

1. **`#1273`-class live-growth guard:** a live file edited after a fold commit (`#1312` closed at
   `12:10:41Z`, live re-mtime `12:09:38Z`, +1,199 B) is a *separate* residual, never an amend of the
   PR that folded an earlier state. Filed by the planner (`#1316` pass: "file it as a fresh finding…
   for the NEXT fold vehicle"). This is that next vehicle.
2. **Wiring + regression landed already**: `#1319` (`make tester-fold-live` target + host-only
   record) and `#1321` (the regression) — this PR is a pure docs fold on top of that, using the wired
   make target.

## Proof at the head

`make tester-fold-live PROFILE=llgenie-tester COPY=1` rc=0; tree == live for both files; the
check-docs / changes-index / lint_linefeeds / wiring chain green at HEAD.
