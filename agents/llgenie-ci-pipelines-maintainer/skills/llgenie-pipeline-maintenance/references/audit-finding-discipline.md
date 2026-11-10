# Filing an own-domain audit finding that is REAL

Depth for the third audit axis named in SKILL.md (`step-sharpening`) and for the rule that
decides whether a candidate gap is filed at all. An audit pass earns its keep only by filing a
gap that reproduces on a live instance — a speculative finding costs the next lane a real review
cycle and teaches the board to distrust this lane's audits.

## Rule: no live witness, no filing — record `measured-clean` instead

A candidate gap must be demonstrated end-to-end on a live example before it is filed. If the
premise cannot be reproduced on a real run/PR/head, the finding is NOT filed; the audit record
says what you risked and why it came back clean:

    MEASURED CLEAN (<axis>): <the hypothesis> — <the live instance you checked> showed <the
    mechanism that refutes it>. Recorded, not filed.

Before filing, ask: **does the mechanism actually work the way the dispatch assumes?** Two
base-rate traps that produce phantom gaps:

- **A wildcard path re-includes the full matrix.** A PR that touches `agents/**` or
  `.github/**` is NOT "docs-only" — those globs re-enter the CI matrix, so its head carries a
  real `ci-images`/`linux`/`guard` set and a real `ci-verdict` from an actual CI run, not a
  scope-only run. A "docs-only PR gets no verdict" finding needs a genuinely docs-only diff;
  inspect each candidate PR's `pulls/<n>/files` before assuming its class from the title.
- **GitHub runs `pull_request` CI on a conflicting head.** A DIRTY/`CONFLICTING` PR still
  executes its PR workflows on the head commit (the merge *ref* fails, the head is valid), so a
  "conflicting PR gets no CI run" premise is false unless measured. A sweep not *starting* a run
  is not the same as GitHub *refusing* one.

A hub docstring that states a premise (`"a DIRTY PR gets no CI run at all"`) is a claim about
code context, not a licence to file around it — re-measure the live mechanism.

## Step-sharpening: prove the gate's failure output omits the identifying datum

The step-sharpening axis asks: *when this gate reds, does its output tell the reader what to
fix?* The high-value, provable subclass is a red that names no identifying datum — a violation
whose `where`/title is a static string or embeds a literal placeholder, so N separate reds read
identically and none points at the thing to change.

Prove it by reading the call chain, not by eyeballing one log:

1. **The verdict function never receives the datum.** Read the signature and its call site —
   e.g. `acceptance_verdict(issue_body_text, pr_body)` has no `n`, and the loop calls it without
   the closing reference, so the issue number cannot appear in any violation it returns.
2. **The `where`/label is static or the evidence holds a placeholder.** `where = "issue-criteria"`
   (same string every time) or evidence that prints a literal `closes #<n>` instead of `closes #123`.
3. **The renderer prints only title + evidence** (`render(items)`), so even a datum the verdict
   held would not reach stdout.
4. **The test suite does not assert the missing datum** — grep the test file for the field
   (`where`, `#N`, a specific issue id). If tests assert only titles/evidence, the omission is
   unguarded and stays; that is the concrete acceptance for the fix (assert the datum appears).

Quote the live measurement that shows the consequence: a real run whose N violations are
all-identical titles, none naming the issue (run id + head sha + the job that printed them).

## The audit record shape

Post the pass on the dispatch/issue thread (and DM the planner) reading:
`re-audited at <main sha> — <K> finding(s) filed; <M> targets measured-clean`, then per axis:
- FINDING (<axis>): **#N** — one-sentence gap, the `scripts/<file>:<line>` root cause, the live
  run/PR that demonstrates it, and that it routes through the normal queue (never implemented by
  this pass, #1088).
- MEASURED CLEAN (<axis>): the hypothesis and the live evidence that refutes it.

Verify the filed issue and the record comment on-wire by direct id before reporting (an issue
that exits 0 from `gh issue create` still needs its body read back; a comment needs
`issues/comments/<id>` read back and confirmed to contain the finding number and the sha).
