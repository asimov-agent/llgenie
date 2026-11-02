# Reading a PR's real state (checks, mergeStateStatus, worktrees, lint scope)

Everything here is about not reporting a state the tooling did not actually return.

## The check rollup is three-valued, not two

`mergeStateStatus` values that matter:

| mss | means | what to report |
|---|---|---|
| `CLEAN` | every required check completed+success, no hold | green |
| `UNSTABLE` | not all required checks conclusively green — usually a check `in_progress`, **or a concluded `failure`** (a non-required check failing also lands here) | read per-run `conclusion`: **pending** if any `in_progress`, **red** if any `failure` |
| `BLOCKED` | red check, missing review/guard, or a `do-not-merge` label | blocked — name which |
| `DIRTY` / `CONFLICTING` | base conflict | rebase (only then) |

A long matrix job (e.g. a ~12m `linux / unit`) keeps the PR at `UNSTABLE` for ten-plus minutes
while every gate-critical check is already green. `UNSTABLE` at that moment is not a failure and
must never be written up as "green and ready". If you need a verdict, wait for the job, then re-read.

**`UNSTABLE` does not distinguish pending from red — and `mergeable` is not `mergeStateStatus`.**
Measured 2026-11-02 (#1525, head `122bb3f9`): `--json mergeStateStatus,mergeable` returned
`UNSTABLE` + `MERGEABLE` in the same response, with `linux/unit` `conclusion=failure` and all 13 other
checks `success`. Two traps fell out of that single read:

- The **`mergeable` field** (`MERGEABLE`) is GitHub's textual-mergeability, not the check gate. Quoting
  it as "the PR is MERGEABLE" is a false status claim while `mergeStateStatus` is `UNSTABLE`. Quote
  `mergeStateStatus` + the rollup, never the `mergeable` field alone.
- A **concluded `failure`** reads `UNSTABLE`, same as `in_progress`. Never infer "still running" from
  `UNSTABLE`; scan the per-run `conclusion` values to say pending vs red.

## `gh pr checks` exit codes lie through a pipe

`gh pr checks` **exits non-zero when any check is pending** (exit 8), and its human table prints
`pending` rows that an `awk '$2=="pass"'`-style filter silently drops. A command like
`gh pr checks N | awk '$2=="fail"||$2=="pending"' ` under `set -e` or with `&&` chaining gives you an
empty or misleading result plus a non-zero exit that looks like a tool error.

Use the API for status/conclusion, and read it programmatically:

```bash
H=$(gh pr view N --repo OWNER/REPO --json headRefOid --jq .headRefOid)
gh api "repos/OWNER/REPO/commits/$H/check-runs?per_page=50" > /tmp/runs.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/runs.json'))
for c in d['check_runs']:
    print(c['name'], '|', c['status'], '|', c.get('conclusion'))
PY
```

`check-runs` returns an **object** with `total_count` + `check_runs`; a `--jq '[...]'` with `select()`
fails with "expected an array but got: object". Also: `gh pr checks --json` has no `status` field
(available: `bucket`, `state`, `link`, `name`, `startedAt`, `completedAt`, `event`, `workflow`), so
`status`/`conclusion` must come from the API.

**The gate before saying green:** every entry in `check_runs` is `status=completed` **and**
`conclusion=success`, and a fresh `--json mergeStateStatus` reads `CLEAN`.

## Field names that are not what you guess

- `gh pr view --json mergedAt` → the merge timestamp; there is **no** `merged` field in the
  available list (`closed`, `closedAt`, `mergedAt`, `mergedBy`). Use `mergedAt` (`null` = open), or
  the REST `pulls/N` payload's `"merged": true/false`.
- REST `pulls/N` gives `mergeable_state` (lowercase, e.g. `unstable`) where GraphQL-style
  `gh pr view` gives `mergeStateStatus` (`UNSTABLE`). Same fact, different spelling — do not treat a
  lowercase REST value as a different status.

## A deleted worktree poisons the persistent shell cwd

The terminal session keeps its cwd across calls. After you `git worktree remove` the tree you were
standing in, every later command fails with `cd: /tmp/wt-XXXX: No such file or directory` (exit 126)
and looks like a broken tool. Pass `workdir` explicitly on the next call (or `cd` to the main clone
in that same command) instead of retrying the inherited cwd.

## Lint scope is the script's repo, not your cwd

`scripts/lint_linefeeds.py` (the `make ci-lint` gate) resolves the repo as `parent.parent` of the
**script file**. Running it by absolute path from another worktree lints the clone that owns the
script, not the tree you meant to check — it returns clean while CI reds on the branch. Run it from
inside the worktree you are checking (`cd $WT && make -s lint`), or copy the script into that tree
and run it there; never trust a "pass" produced from a foreign cwd.

## Live-file folding: stability before bytes, current before quoted

Before folding a live agent-profile file into the tree:

1. Measure mtime **twice, seconds apart**; if it moved, another lane is still authoring it — wait.
2. Hash the live file at read time and compare against the tree blob after writing (`cmp`), never
   against a hash quoted in a message: a quoted hash is stale by the time it is read.
3. Byte size and **character** size differ for multibyte markdown; a 100k *char* cap can pass while
   `wc -c` reads over 100k. State which you measured.

## A merged PR is not a green merged result — the post-merge push run is a second run

`gh pr merge` does not prove the merged result is green. The CI that ran on the PR head proves the
head; the merge commit triggers a **fresh push run** that starts only after the merge and finishes
minutes later. When acceptance says "green at the PR head AND on the merged result", those are two
separate measurements — never quote the PR-head rollup as merged-result evidence, and never write
"merged-result accepted" while that push run is still `in_progress`.

- Find the push run at the merge commit:
  `gh api "repos/O/R/actions/runs?head_sha=<mergeSHA>" --jq '.workflow_runs[] | "\(.id) \(.name) \(.status) \(.conclusion // "")'"`.
- A `liveness` (or other single-job) run at the head is **not** the CI run — match on the workflow
  that carries the failing leg (`linux / unit`, etc.), not on "a run exists at this sha".
- Verify **job-level**, not just the run verdict: an acceptance that names a specific leg needs the
  job read too — `gh api "repos/O/R/actions/runs/<run>/jobs?per_page=100" --jq '.jobs[] | "\(.name) -> \(.conclusion)"'`.
  The leg that was red must read `success` at the merged head; a `conclusion=success` run verdict
  alone does not prove the one job you were asked about recovered.
- The workflow-run API returns `id` (the run id); there is no `database_id` field — use `id`.

A long matrix outlives a foreground poll. Launch a bounded background loop
(`terminal(background=true, notify=[...])`) that reads `status`+`conclusion`, then wait on that
process to a terminal verdict instead of re-polling in the foreground until the tool times out.

## Reproduce a CI failure on a clean worktree at the exact head — a dirty checkout lies

A red CI run at head `X` while your local clone shows green almost always means the clone is not at
`X` or is dirty. Do not debug from it. Cut a detached worktree at the exact failing sha and re-run
the failing check there:

```bash
git fetch origin +refs/heads/main:refs/remotes/origin/main >/dev/null
git worktree add /tmp/wt-accept --detach <failing-sha>
cd /tmp/wt-accept && <the failing check>
cd - >/dev/null && git worktree remove /tmp/wt-accept --force && git worktree prune
```

Pass `workdir` on every later command (see the deleted-worktree cwd trap above). A "PASS" from a
dirty or stale clone measures the wrong tree — it is not a refutation of the CI.

## A folded file that references a sibling folded file is stacked, not parallel

If the file you fold names other references (a pointer array, an index line) whose content lands in
a different PR, the `skill-reference-missing` gate reds your PR until those refs are in your tree.
Order it: land the referenced refs first, then rebase your PR onto them, then verify every named
path exists in-tree (`git ls-tree` / `git cat-file -e`) before pushing.
