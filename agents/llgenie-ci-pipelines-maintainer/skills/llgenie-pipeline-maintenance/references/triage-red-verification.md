# Triaging a red: verifying the head, the verdict, and the landed change

Always-on rules (short form):

- **A dispatch that names a head sha is a claim about a past moment.** Before acting on it (amend, force-push, report, close), re-derive the live head three ways — `gh pr view <n> --json headRefOid`, `git ls-remote origin <branch>`, `git rev-parse HEAD`. Disagreement means the dispatch is stale: re-measure its premise against the LIVE head first. A "fix this commit message" ask is often already satisfied at the current head — the cited sha is the pre-fix one.
- **An aggregate-verdict FAILURE posted while any check is still `in_progress` is transient, not settled.** `ci-verdict` can post before a long matrix leg (e.g. `linux / unit`, 12+ min) concludes, so the rollup reads FAILURE/UNSTABLE mid-flight and flips to SUCCESS once the leg finishes. Never call such a red "ambient" or "the known <x> issue" until every check is `completed`; read the verdict's own summary rather than the rollup colour.
- **Verify the change on the MERGED tree, not the PR head.** For a merged PR the deliverable is the squash commit on `upstream/main`. A green PR-head check-run is evidence of intent; the merged commit is proof.
- **Never fabricate or re-apply a change to clear a completion guard.** If a "make the task-relevant change" guard fires but the change is demonstrably on the merged tree, the honest disposition is the merged-tree evidence (commit sha, close-count, stat) — do not rewrite a merged commit or manufacture a no-op.

## 1. Is the head the dispatch named still live?

```bash
gh pr view <n> -R asimov-agent/llgenie --json headRefOid --jq .headRefOid
git ls-remote origin <branch> | awk '{print $1}'
git rev-parse HEAD            # in the PR's own worktree
git log -1 --format=%B HEAD | grep -c 'closes #<n>'   # 1 = adjacent close present, 0 = missing
```

## 2. Is the red settled or mid-flight?

`gh pr checks` prints TAB-separated: `name<TAB>conclusion<TAB>duration<TAB>url`. A `pending`/`0s` row has NOT concluded — an aggregate verdict is not final while any check runs.

Authoritative per-check state (works when the rollup shows an empty row):

```bash
gh api "repos/asimov-agent/llgenie/commits/<full_sha>/check-runs?per_page=100" \
  --jq '[.check_runs[] | (.name)+"="+(.conclusion//.status)] | join("  ")'
```

`statusCheckRollup` (via `gh pr view --json`) uses `status: IN_PROGRESS` / `conclusion: ""` for a running check — an empty conclusion there is **pending**, not red.

## 3. What does ci-verdict actually object to?

```bash
gh api "repos/asimov-agent/llgenie/commits/<full_sha>/check-runs?per_page=100" \
  --jq '[.check_runs[] | select(.name=="ci-verdict")][0] | .output.summary'
```

A summary ending `pending=N` with healthy scopes means the verdict ran too early — re-read after the long leg completes instead of filing a standing defect. A `ci-verdict` check-run can be *re-posted* for the same sha; the newest one is the record.

## 4. Did the change land — on the merged tree?

```bash
git fetch upstream main
git log upstream/main --grep='<pr title fragment>' --format='%H %s' | head
C=$(git log upstream/main --format='%H' --grep='<pr title fragment>' | head -1)
git show -s --format=%B "$C" | grep -c 'closes #<n>'    # adjacent close on the squash
git show --stat --format='' "$C"                         # the substantive diff
```

## 5. When gh/jq output looks empty (the stdout heisenbug)

Do not re-run the identical pipe more than once. Save the payload, parse with python:

```bash
gh api "<endpoint>" > /tmp/payload.json 2>&1
python3 - <<'PY'
import json
d=json.load(open('/tmp/payload.json'))
print('count', len(d) if isinstance(d,list) else d.get('total_count'))
PY
```

Real causes: a jq expression with a stray concatenation (quote error), a warning line before the JSON, or a field name that differs between REST and graphql shapes (`status` vs `conclusion`, `IN_PROGRESS` vs null). Save-then-parse sidesteps all three. `cat` of a file that parsed fine in python is not evidence it is empty — the reader and writer can differ.
