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

## A stale dispatch can name an issue that ALREADY has a live vehicle — verify that vehicle, never open a parallel PR

A dispatch (planner DM, queue item) encodes the board as it looked when written; by the time you
act it can be superseded or recalled. Two checks before any worktree:

- Read the issue's FULL thread, not just the body. A `Dispatch RECALL`, a peer lane's claim, or a
  reviewer write-back ("all ACs ticked at head `<sha>`") is the durable record and outranks the DM.
- Search for an existing vehicle:
  `gh pr list --repo <o>/<r> --search "<issue#> in:body" --state open --json number,headRefName,headRefOid`
  plus `gh pr list --head <suspected-branch> --state all`. An open PR whose body closes the issue
  IS the one vehicle (#824) — a second PR is a duplicate, not a contribution.

When a vehicle exists and another lane owns it, do NOT drive it. The deliverable becomes a
**guard-prove**: measured evidence that the vehicle's live head satisfies the issue's criteria.
Measure at the head that will merge, not the sha the issue body cites (a tick routinely cites an
earlier commit on the same branch, or a branch that moved on afterwards):

1. `gh pr view <n> --json headRefOid,headRepositoryOwner,mergeable,state`. A fork head
   (`headRepositoryOwner` != upstream) must be cloned from the FORK URL, not upstream.
2. Run the named suites at that head, in the test image:
   `docker run --rm -u root -e HOME=/root -v "$PWD":/repo -w /repo llgenie/test:latest python -m pytest tests/<file> -q`
3. Verify the static contract the criteria name as well — a test pass does not prove a YAML
   contract (workflow triggers/inputs/concurrency, job id collision, `make openspec-validate
   NAME=…`, a no-skip guard test).
4. Post the guard-prove on the ISSUE with the head sha, suite counts and exact commands, and say
   explicitly that no parallel PR was opened.

Reading a GitHub Actions workflow with PyYAML: YAML 1.1 parses a bare `on` key as the BOOLEAN
`True`, so `yaml.safe_load(f)["on"]` raises `KeyError: 'on'`. Use `d.get(True) or d.get("on")`
before indexing `workflow_dispatch` / `inputs`.

## A dispatched "orphan branch" may be STACKED on an unmerged PR — a standalone main PR is then structurally impossible

An "orphan branch, no PR, rebase onto main and open one" dispatch presumes the branch stands
alone. Check the opposite first: are the branch's EARLIEST commits another OPEN PR's own commits?
`git log --oneline <branch>` and compare subjects, and `git merge-base --is-ancestor <other-pr-head>
<branch>` (exit 0 = the branch is built on that PR). A branch cut from an unmerged PR inherits its
commits as the base; rebasing it onto main drags the other PR's work along — a second vehicle for
work another PR already owns (#824).

The decisive check is whether the file/job/symbol the branch's UNIQUE commits edit even exists on
main: `git -C <canonical> show origin/main:<path> | grep -c <job-id-or-symbol>`. When the change
ATTACHES to a job or block that exists only inside the other PR's diff (0 matches on main), a
standalone PR against main is inert — its hunk has nothing to attach to — AND it duplicates the
other PR's base. Rebasing such a branch reds on files it never meant to touch, which is the tell
that the base, not the change, is wrong.

Correct move: do NOT open the standalone PR. Cherry-pick only the branch's UNIQUE commits onto the
other PR's CURRENT head (`git cherry-pick <sha> <sha>`); it usually applies clean — resolve only
changelog/index row-add conflicts by keeping BOTH sides. Then record the fold head, post the
measured finding on the issue (branch@sha, base=<other-PR-head>, fold=<fold-sha>), and hand the
fold to the lane that owns that PR. Never push to another lane's PR branch — the owner lands it.

### When a re-dispatch repeats the impossible standalone premise

A queue item or planner DM can re-send the SAME canned "rebase onto main, open the ready-for-review
PR" wording AFTER you already reported (with evidence) that a standalone main PR is impossible — it
re-encodes the board, it does not absorb your finding. Do NOT manufacture a main-based PR to satisfy
the canned wording: that is exactly the inert/duplicate vehicle (#824) the section above forbids,
and it will be a hunk with nothing to attach to.

The satisfiable one-vehicle deliverable is a **stacked PR on the dependency's branch**:

1. Push the fold head onto the EXISTING orphan branch name — do NOT invent a new branch (that would
   be a second vehicle); "one vehicle" means the branch that already exists.
2. Open it with the dependency PR's branch as base:
   `gh pr create --base <dependency-PR-branch> --head <orphan-branch> --title ... --body-file ...`,
   body `closes #<issue>`. Its diff vs that base is exactly the orphan's UNIQUE commits (verify with
   `git diff --stat <dependency-head> <fold-head>`); it merges only after the dependency PR does
   (GitHub retargets the stack to main on that merge). Confirm not-draft + MERGEABLE/`UNSTABLE`
   (base≠main), never MERGEABLE-vs-main.
3. Report **base=<dependency-branch>** and the why-not-main evidence (0 matches on `origin/main`
   for the job/block the change attaches to), so the base choice is auditable, not silent.

Force-pushing the orphan branch to the fold head while it is checked out in another lane's worktree:
use `--force-with-lease=<branch>:<measured-wire-sha>` (fetch immediately before, tag the sha you
measured) and only after that lane has handed the branch off (prepared, not actively driven). A
branch a lane is actively driving is read-only — propose a patch as a comment, never rewrite it.

## Why this recurs in this repo

Store/view tests are converted to invariant style ("assert rules, not rows") by design. Once the
store lands and those families are invariant-form, the issue's snapshot-era failure count stops
reproducing — and manufacturing content-pins back in would re-break the very robustness the refactor
bought. So a stale "N failures" issue is usually evidence the fix already shipped, not work owed.
