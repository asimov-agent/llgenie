# Designing and verifying a CI gate

Rules for adding a gate to a gated repo, and for judging whether a reported green is real.

## Gate the invariant, not the file

"A change must not touch <file>" is almost always the wrong rule for a *generated or aggregate* file: every contributor legitimately regenerates it, so the rule reds every open PR the moment it lands. Assert the derived property instead — e.g. *every row in the aggregate must correspond to a source fragment* — which fails hand-edits and duplicated rows while passing any honest regeneration.

Before adding such a rule, enumerate the open PRs' diffs for the file it would forbid. If most touch it legitimately, the rule is wrong, not the PRs.

## Check the retro-red surface before merge

A gate added to a shared CI job runs on **every** open PR on its next run, not only on new ones. If that would red existing work, decide the cut-off (grandfather by base sha, or narrow the invariant) **before** writing the tests. A gate that reds the whole board on merge gets disabled by the first person it blocks.

## One default per policy

A default belongs where the policy lives. If the build file already supplies it (`VAR ?= origin/main`), do **not** also default it inside the script: the second default makes the acceptance control insensitive — the test passes whether or not the build-file line exists, so deleting the real policy becomes invisible. Require the argument in the script and let the variable be the single source; make a direct call fail with a message naming the build-file default.

## Verify which paths actually run it

Read the build recipe and the workflow that invokes the target — a gate can be reached by a CI job *and* a pre-push hook, which changes both the coverage claim and the environment it runs in (env vars differ between the two). Do not infer reachability from a workflow file alone; the recipe is the authority.

## A selection is not a verdict

A test excluded by a marker or an exclusion list has not passed. Before calling a suite green, run the excluded test explicitly (`-m <marker>`, `-k <name>`) at the same head. Report a green that comes from exclusion as "green with X deselected", never as "fixed". Conversely, a marker under a *failing* test hides a regression: prove the marker is honest by showing the test executes and passes.

## Golden fixtures follow behaviour

When a behaviour change intentionally alters the output a golden file records, regenerate it with the repo's own render target and quote the governing criterion in the commit. Then check the diff is scoped — only the rows the change affects. A wholesale rewrite means the regeneration absorbed unrelated drift and must be investigated, not committed.

## Never ask contributors to regenerate a shared file before pushing

An instruction to run a render/regenerate step in a change branch makes every PR rewrite one shared file, which manufactures merge conflicts for everyone else. A change adds its own source fragment; the publish step renders.

## Verify gates by execution in a throwaway tree

Run the gate bare (no pipe, real `$?`) in an extracted tarball or a scratch copy, not in a worktree and not by reading the code. Quote `rc=<n>` and the message. Reading a gate and agreeing with it is not verification; two independent runs on the same head turn "the gate still bites" from a report into a fact.

## Counting: only trust a number that can vary

When verifying a selector or filter that returns records with a flag (`[(name, selected, why), …]`), count the **flag**, not `len(rows)` — the row count is constant by construction and measures nothing. A metric that returns the same value for every input is not a measurement: if an empty input, a one-item input and a full input all print the same figure, the figure is the container, not the answer.

## Measure against the branch's own base

A cumulative diff against the trunk and a branch's own diff give different answers about what the branch changed, and quoting the wrong one produces a false accusation — or a false clearance. A branch stacked on another PR carries the base's changes in its trunk diff. Always name the base you diffed from, and prefer the branch's own base when asking "did this PR touch X".

## A verdict belongs to the sha it ran on

A check result names one commit. After a rebase, replay or peer repair the old verdict does not carry, even when the content is byte-identical — re-read `pulls/<n>.head.sha` from the API and require the verdict at that sha. When a head moves, every "clean", "green" or "blocked" statement about it expires.

## Run the subcommand the recipe runs, not the one the docstring documents

A script with several subcommands can have a documented one that is a *report*, not the gate. Measured shape: the
usage block listed `check` and `report` but the CI recipe ran `ratchet` — and `check` printed 84 per-file findings
and exited 1 on a clean trunk, while `ratchet` compared against the baseline and exited 0. Following the docs produced
a confident false red on an untouched `main`.

- Read the build recipe for the exact argv CI passes (`grep -n '<target>' Makefile`), then run **that**.
- Where a report and a gate share a code path, the report reds on legitimate grandfathered debt; running it as the gate
  makes a migration look unfinished forever.
- When the docs and the recipe disagree, the defect is the docs — file it. A lane that follows the usage block will
  either "fix" permitted debt or learn to ignore a gate that was telling it nothing.

## Membership in the fast-gate list is the coverage claim

A pre-push or preflight tool that imports the repo's fast-gate tuple **runs exactly those gates**, whatever its own
docstring says about "the gates CI already covers". Measured shape: a preflight whose prose cited a ratchet among the
covered gates while that gate sat in a deferred mapping — so four separate PRs each paid a full 25-minute matrix to
learn the same two-line style defect.

- Before trusting a tool's coverage claim, print the list it actually iterates (`sed -n '<tuple>p'` on the source).
- **Do not widen a pinned fast-gate list inside a feature PR** when a test asserts the list exactly, order-pinned:
  that is editing the acceptance test to fit the change. File the widening as its own issue, and correct the false
  claim in the same breath — a false coverage claim is worse than a missing gate.
- Add a pinning test that asserts the *current* classification (gate X deferred, not fast) with a negative control
  (temporarily add it to the fast tuple → the test reds), so the claim cannot drift back silently.

## A gate that returns on the first failing class hides the rest

A linter that `return 1`s on the first defect class it meets reports one fault for a file that has three, so a single
file presents as a sequence of discoveries rather than a set. When several rounds of "fixed it — now a different
failure in the same file" occur, suspect the gate's control flow before suspecting bad luck, and file the masking as
its own defect rather than editing it on the way past.

## New files follow the tree's import convention from the first commit

Where a repo has migrated to a single import root (a conftest seam) and gates the migration with a count-based
ratchet, a **new** test file that adds its own `sys.path.insert` plus bare module imports is refused even though every
pre-existing file does the same — the baseline covers grandfathered files, not new ones. The failure text is an
aggregate count (`bare: N now, M recorded`) that names no file, so the fix is found by diffing the gate's own findings
between clean trunk and the merged tree, or by checking which of the PR's files is absent from the trunk.

- Write new tests in the migrated form from the start: `from <pkg> import <module>` with no per-file root.
- The seam often fixes a second bug: a bare import can bind a *different module object* than the package import, so an
  identity assertion (`x is y`) between two import paths passes or fails for the wrong reason. The package form is the
  one that makes identity mean what it says.
