# Census / scope gate: "pointer not an ancestor" is usually a shallow-worktree false positive

## The mechanism

The architecture-census gate (`scripts/check_architecture_census.py`) resolves the doc's
`measured at <sha>` pointer by three steps: (1) confirm the sha is a real commit, (2) check its
named file:line content still says what the doc cites, (3) require the pointer to be an
**ancestor of the branch HEAD**. Step 3 is where a shallow clone breaks it.

Run inside a worktree carved from a **shallow clone** (`git rev-parse --is-shallow-repository`
returns `true`), a far-back pointer sha was never fetched into the object store. `rev-parse`
of the sha fails or the ancestry walk cannot reach it, so the gate exits non-zero and prints
`no usable pointer` / `pointer <sha> is not an ancestor` — even though the **official CI**,
which checks out with `fetch-depth: 0`, passes the exact same head.

## The rule

When a lane discloses a `census`/`scope`/`check-docs` red, **do not accept it as a board defect**
and do not file an issue on the PR's behalf. Measure the **real PR head** yourself:

```bash
gh pr checks <n> --repo <o>/<r>          # look at scope / census / check-docs
gh api repos/<o>/<r>/commits/<head>/check-runs --jq '[.check_runs[]|{name,conclusion}]'
```

- If the gate is **green at the real PR head**, the lane's red is an artifact of its own shallow
  worktree. Tell the lane to `git fetch --unshallow` (or `git fetch --deepen=<N>`) and re-run
  before it reports again.
- Only file a systemic gate issue if CI itself is **red at that head** — i.e. the failure
  reproduces in a full checkout, not only in the lane's worktree.

## Why a pointer re-pin does NOT fix it

A prior resolution on this class was a pointer **re-pin** (put a new `measured at <sha>` commit
on main). That fixes a genuinely stale pin; it does **not** touch the shallow-worktree mechanism,
so the same false red returns on the next fresh main-cut head the lane measures. The durable fix
is either (a) unshallow the lane's tree, or (b) harden the gate to detect `--is-shallow-repository`
and fail with a distinct "cannot verify ancestry: shallow checkout" message instead of a
misleading "not an ancestor".

## Cross-checks that keep you honest

- Quote the check-run **name + conclusion** and the head sha you measured; a lane's prose is not
  evidence (see `verifying-lane-claims.md`).
- A `scope` red from a lane is worth the same suspicion as a `census` one — both consume the
  pointer.
- If you cannot reproduce the red in your own full clone, say so and name the clone depth you
  measured against; "cannot reproduce in a full checkout" is itself the finding.
