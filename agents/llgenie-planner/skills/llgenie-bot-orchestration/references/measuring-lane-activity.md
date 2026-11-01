# Measuring lane activity and querying workflow runs

How to answer "which lane is idle / when did this bot last run / is that red fresh?" from the API,
and the `gh` query traps that make the obvious commands lie.

## 1. `gh run list --workflow <file-stem>` almost always fails

`--workflow` matches the workflow's **display `name:` in the YAML**, which for this fleet is a long
descriptive sentence ("rebase-bot — keeps every open PR current with main, every eligible PR per run
(never merges)"), not the filename. So `gh run list --workflow rebase-bot` returns
`could not find any workflows named rebase-bot`. Do not conclude the lane has no runs — resolve the
numeric id from the path instead:

```bash
id=$(gh api "repos/$OWNER/$REPO/actions/workflows?per_page=100" \
  --jq '.workflows[] | select(.path|contains("rebase-bot")) | .id')
gh api "repos/$OWNER/$REPO/actions/workflows/$id/runs?per_page=5" \
  --jq '.workflow_runs[] | "\(.id) \(.status)/\(.conclusion) \(.created_at)"' | head
```

Match on `.path` (`.github/workflows/<file>.yml`) with `contains(<stem>)` — an exact `==` against
the filename stem fails because `.path` carries the full `.github/workflows/` prefix.

## 2. The runs payload is `.workflow_runs`, the list payload is `.workflows`

Both endpoints return an **object** at the root (`{"total_count":N,"workflow_runs":[…]}`, `{"total_count":N,"workflows":[…]}`),
not a bare array. Piping `.[]` or `.[0]` straight onto the response gives
`expected an array but got: object`. Always descend: `.workflow_runs[0]`, `.workflows[]`.

## 3. `created_at[11:16]` shows time-of-day only — a stale red masquerades as fresh

Slicing `created_at` to `[11:16]` drops the **date**. A run from five days ago and one from five
minutes ago both print `13:50`. Before you treat a workflow's newest run as a live red, dispatch on
it, or file an issue about it, read the full `created_at` (or the run log's own timestamps) and
confirm it postdates the merges/changes you care about. A red older than the work it would explain
is a **stale** run — the lane simply has not run since — not a fresh finding.

```bash
gh api "repos/$OWNER/$REPO/actions/workflows/$id/runs?per_page=1" \
  --jq '.workflow_runs[0] | {id,status,conclusion,created:.created_at}'
gh run view <run-id> --log-failed 2>/dev/null | tail -15   # log lines carry their own ISO dates
```

## 4. Per-workflow sweep for a true idleness census

Loop the workflow list once and print newest-run state per lane; this is the measured answer to
"who is quiet right now", and it replaces guessing from a flat `--limit N` window (which interleaves
lanes and hides the low-frequency bots):

```bash
for id in $(gh api "repos/$OWNER/$REPO/actions/workflows?per_page=100" \
  --jq '.workflows[] | select(.path|test("bot|sync|bump|refine|rebase|security|scan")) | .id'); do
  nm=$(gh api "repos/$OWNER/$REPO/actions/workflows/$id" --jq '.name' | cut -c1-24)
  last=$(gh api "repos/$OWNER/$REPO/actions/workflows/$id/runs?per_page=1" \
    --jq '.workflow_runs[0] | "\(.status)/\(.conclusion) \(.created_at)"')
  printf '%-26s | %s\n' "$nm" "$last"
done
```

A lane whose newest run is `completed/failure` because its last scheduled slot hit an ambient
main-red (a shared `make ci-unit` failure, not a lane defect) is not idle-and-broken; separate the
ambient gate failure from the lane's own behaviour before filing on it.
