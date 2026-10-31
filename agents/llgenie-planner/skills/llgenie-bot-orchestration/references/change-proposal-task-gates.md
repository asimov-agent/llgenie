# Change-proposal task gates: what a checkbox can and cannot claim

Repos that gate merges on an `openspec` change's `tasks.md` run two checks that interact badly when a checkbox is treated as prose:

- `openspec-tasks-check` — wired into **both** `scope` and the `linux/openspec` leg — fails on **any** unchecked box, naming the offending line numbers.
- `openspec-validate NAME=<change>` fails on a malformed proposal.

So a checkbox is a **gate input**, not a note about progress. Two rules follow.

## Never tick a box citing work verified at a different sha

A box that reads "`make test-unit` green" may be ticked only when a **completed** run **at that head** concluded success. Ticking from a local run, from a run at another sha, or from a locally-observed clean suite produces the false-tick class: the box asserts a gate nobody has seen pass on the tree that will merge.

Local and CI environments are not interchangeable — a tokenless local container failing live-service probes says nothing about a CI job that injects the credential, and vice versa. Quote the job id with its summary counts instead of either environment's impression.

## An honest untick makes the PR unmergeable — that is correct, plan for it

Unticking a box that is not yet true (the suite is red) is the right call, and it **immediately reds `scope`/`openspec`**, because any unchecked box fails the task check. Do not fight that by re-ticking; the sequence that ends green is:

1. fix the underlying failures until the gate's own command passes;
2. wait for the leg to conclude **at that head**;
3. only then **re-tick in a separate commit**, so the tick has its own sha and the run it cites;
4. the following run clears `scope`.

A tick and the run it cites in one commit are indistinguishable to a reviewer; two commits make the claim auditable. When a lane reports a `scope` red that is *only* an unchecked box, that is not a defect to route — it is the gate correctly refusing an unproven claim, and the remedy is the four steps above.

## Do not weaken the assertion to make a count drop

When a code change makes test expectations stale, thread the new parameter through the call sites — small net-positive diffs — rather than rewriting the expectation to match new output. If the observed outcome genuinely changed, the commit must name the acceptance criterion that authorises it; otherwise a regenerated fixture is indistinguishable from a covered-up regression, and no reviewer can tell which they are looking at.
