# Measure the issue's remaining scope before writing code

A well-written issue records the failure SEEN when it was filed — a store snapshot, a test count, a
red gate. By the time it is dispatched, other PRs may already have landed the fix. The brief's
stated cause is a CLAIM, not a fact: verify it on a fresh worktree off `origin/main` before you
write a line, and never trust a number ("101 failures", "23 models") quoted in the issue body.

## Steps

1. Fresh worktree off the fetched `origin/main`; write the sha you branched from into your start
   comment. Never start from a branch or sha you already had.
2. Run the exact gate/acceptance the issue names — on the CURRENT tree. If the issue says
   `make test-unit` has N failures, run `make test-unit` and read the real pass/fail counts.
3. Run the rest of the named gate sequence hermetically (snapshot/replay, no live services) to prove
   whether the WHOLE class is green, not just the one gate the title names. A single green gate can
   hide a still-red sibling.
4. Compute remaining scope. Read the issue's own thread/close condition — the owner often wrote one
   (e.g. "leave open UNLESS <store landed> AND <gate is green on it>"). If every named condition is
   already met on the current tree, remaining scope is EMPTY.

## A claim of ABSENCE is the highest-risk claim — measure it at `origin/main` head, never in a stale or partial checkout

"There is no cross-run cache", "that field does not exist", "no test covers this" — an absence
claim is verified by reading a file, so it inherits whatever the checkout you read actually
contained. A worktree or clone that is behind `origin/main`, or is a partial/sparse checkout that
dropped the path, silently OMITS the file and produces a confident, wrong negative. Never assert a
mechanism is missing from one `grep`/`ls` in whatever directory you happened to be in.

- Resolve the file AT the pinned head first: `git -C <repo> show origin/main:<path> | grep <sym>`
  (or open the file in a worktree you cut from the fetched `origin/main` this session). "No such
  file" from a `grep` is a fact about your checkout, not about the repo.
- If a path is missing, that is a signal to fetch/verify, not a licence to write "absent". Confirm
the file is tracked: `git -C <repo> ls-files <path>` — an empty result on a stale clone that also
lists no siblings is the stale-tree tell.
- State the sha you measured at alongside any absence claim, so a wrong negative is catchable.

## If remaining scope is empty: report a measured no-op, do NOT manufacture a PR

Opening a PR that edits tests or generated artefacts to "look busy" when the gate is already green
is test-text churn — the exact thing the invariant-test rule forbids (never edit an assertion to
match code; never widen a test just to produce a diff). The deliverable of a measured-empty dispatch
is a report to the planner, not a branch.

- State the measurements with numbers: `generated_utc` + row count of the store, `make test-unit`
  pass/fail counts, each hermetic gate's verdict, and the count of previously-failing files that now
  pass on the current store.
- Quote the issue's own close condition and show each clause is met.
- Recommend closure — but do NOT close the issue yourself from the implementer lane unless that lane
  is explicitly charged with closing; owner/planner holds that authority. Do NOT open or arm a PR.
- Name the prior PRs that already did the work so the audit trail stays intact.

## Why this recurs in this repo

Store/view tests are converted to invariant style ("assert rules, not rows") by design. Once the
store lands and those families are invariant-form, the issue's snapshot-era failure count stops
reproducing — and manufacturing content-pins back in would re-break the very robustness the refactor
bought. So a stale "N failures" issue is usually evidence the fix already shipped, not work owed.
