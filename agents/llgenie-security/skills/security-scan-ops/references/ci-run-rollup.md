# Reading a PR's real CI rollup

`gh pr checks <n>` is a pull-request-scoped view and is NOT the run inventory. It omits a
workflow that **failed at evaluation** (0 jobs) and it can show only the `guard`/`holds`/`scope`
checks while the main `ci.yml` matrix run sits failed beside it. Treat any rollup you assembled
from `gh pr checks` alone as unproven; corroborate with the run list for the exact head sha.

## The two-command rollup

```bash
SHA=$(gh pr view <n> --repo <o>/<r> --json headRefOid --jq .headRefOid)
gh run list --repo <o>/<r> --commit "$SHA" \
  --json databaseId,name,status,conclusion,event \
  --jq '.[]|"\(.databaseId) \(.name) \(.status)/\(.conclusion) \(.event)"'
```

`gh run list` has **no `--head` flag** (it errors `unknown flag`); use `--commit <sha>`.

## A `failure` run with ZERO jobs is a workflow-file issue, not a red test

```bash
gh api repos/<o>/<r>/actions/runs/<run-id>/jobs --jq .total_count   # 0 => evaluation failure
```

GitHub annotates such a run "This run likely failed because of a workflow file issue". Characteristics:

- The YAML **parses fine locally** (`yaml.safe_load` succeeds) — local parsing does NOT disprove it.
  Evaluation is caller-side: permissions, the reusable-workflow contract, and secret declarations.
- It is **deterministic**, not transient: the same failure repeats on every head that carries the
  offending workflow file, including `main` after merge.
- `gh pr checks` may not list it at all; `gh api .../commits/<sha>/check-runs` may show only the
  non-ci workflows (`merge`, `recheck`, `liveness`). Absence from those views is not absence of a red.

Diagnose by comparing the caller job with the callee workflow it `uses:`:

```bash
git show <sha>:.github/workflows/ci.yml > /tmp/ci.yml
python3 -c "import yaml;d=yaml.safe_load(open('/tmp/ci.yml'));j=d['jobs']['linux'];print(j.get('uses'),j.get('permissions'),j.get('secrets'),j.get('with'))"
```

### The reusable-workflow contract (the usual cause)

1. A called workflow can never be granted **more** than the caller passes. Every `permissions:` the
   callee declares must also be named in the caller job, or GitHub refuses the whole workflow
   (0 jobs, nothing to open).
2. Replacing `secrets: inherit` with an explicit `secrets:` block passes **only the named keys**. If
   the callee (`pipeline.yml` or similar) consumes a secret the caller no longer lists, the call is
   rejected at evaluation. Check the callee's `required:` secret declarations against the caller's map.
3. A workflow-level `env:` holding a secret that the security scan flags is a real reason to move it
   to each job's own env — but a `secrets:` narrowing done in the same pass is the change that breaks
   the call. Review the two halves separately.

The fix belongs to the lane that owns `.github/workflows/*`. File/report it with the failing run id and
sha, name the caller/callee pair, and hand it off — a workflow file this lane does not own is not a
patch this lane writes.

## `mergeCommit` is an object

`gh pr view <n> --json mergeCommit --jq '.mergeCommit[0:10]'` errors
`expected an array but got: object`. Use `--jq '.mergeCommit.oid[0:10]'`.

## A squash merge is not a descendant

A squash-merged PR produces a NEW commit on the base; the branch head is not an ancestor of it, and
`git merge-base --is-ancestor <branch-head> <main-head>` fails on a correctly merged PR. Prove a merge
landed by state, not ancestry: `gh pr view <n> --json state,mergedAt,mergeCommit` (`MERGED` +
`mergedAt`) and the issue's `state` (`gh issue view <n> --json state` → `CLOSED` when the closing
keyword fired). Do not claim a fix is unlanded because the ancestry check red.
