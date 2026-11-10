# Triaging a red CI check before you file or fix

A red on an open PR has one of two causes: the branch base is stale (a fix already on main is missing from the head), or the PR itself has a genuine defect. Classify first — filing an issue for a stale-base red spawns a duplicate vehicle that another lane already owns.

## Procedure

1. **Read the failing STEP, not the badge.** `gh api /repos/<org>/<repo>/actions/jobs/<job_id> --jq '[.steps[]|select(.conclusion!="success")|{name,conclusion}]'` names the exact failing step (e.g. `make ci-unit`). The `.../actions/jobs/<id>/logs` route can come back empty to a grep; the steps API always answers.
2. **Find the job/run id.** From `gh pr view <n> --json statusCheckRollup`, each check carries a `detailsUrl` of the form `.../runs/<run_id>/job/<job_id>`.
3. **Is the fixing commit already on main, merely absent from the head?**
   `git merge-base --is-ancestor <fix-merge-sha> <pr-head>; echo $?`
   - `1` = head predates the fix → stale base.
   - `0` = fix present → a still-red check here is a genuine new failure.
4. **Do the PR's own commits touch the failing file?** `git log --name-only <base>..<head>`. Untouched file ⇒ the red is the base's, not the PR's.
5. **Route by the result.**
   - Stale base → hand the rebase to `llgenie-pr-merge-conflict` with the head sha and the run id; do NOT file a new issue, and never rebase it yourself (this lane does not rebase).
   - Fix present but still red → genuine new defect: file/own it in this lane.

## Pitfalls that cost real time

- A run that STARTED before a fix merged, on a base lacking the fix, is stale even if it CONCLUDED after the merge. Compare the run's start time and its base, never the conclusion time alone.
- A worktree's local `main` ref can lag the truth (e.g. `git show main:<path>` says the file "exists on disk, but not in 'main'"). Verify file state against the fetched `upstream/main`: `git show upstream/main:<path>`. Confirm the fix's ancestry with `git merge-base --is-ancestor <fix-sha> upstream/main`.
- A cancelled run reads as `fail` in some rollups and a job that cannot load has zero jobs — always open the steps, not the colour.

## A workflow that fails to LOAD — 0 jobs, 0 check-runs, path-named run

A workflow GitHub **rejects at compile/startup time** is worse than a red one: the run is
`completed/failure` with **0 jobs**, its check-suite has **0 check-runs**, `gh pr checks` shows
no row, and the run's `name` is the **workflow file path** rather than the workflow's `name:`.
Treat that signature as a load failure, not "CI pending" or a missing run.

**The literal reason is in the check-run `output.title`, not in the run/jobs API.** The jobs
endpoint returns empty (nothing started) and the run page will not give it up; fetch the
check-suite, then its check-runs, and read `output.title` — that carries the annotation, e.g.:

    Invalid workflow file: .github/workflows/ci.yml#L310
    error parsing called workflow ... : secret name GITHUB_TOKEN within workflow_call
    can not be used since it collides with system reserved name

```
gh api repos/<o>/<r>/commits/<full-sha>/check-suites --jq '.check_suites[]|{id,conclusion}'
gh api repos/<o>/<r>/check-suites/<id>/check-runs --jq '.check_runs[]|{name,conclusion,title:.output.title}'
```

### Reserved secret names in `on.workflow_call.secrets`

A reusable workflow **cannot declare a secret named `GITHUB_TOKEN`** (or any other
system-reserved name) in `on.workflow_call.secrets` — GitHub rejects the whole file at load.
Alias it at the call boundary instead, and declare only the alias:

- caller (`uses:` job): `secrets: { RUN_TOKEN: ${{ secrets.GITHUB_TOKEN }} }`
- callee `on.workflow_call.secrets`: declare `RUN_TOKEN` (never `GITHUB_TOKEN`)
- inside the Hub-touching job: `env: { GITHUB_TOKEN: ${{ secrets.RUN_TOKEN }} }` to re-export
  the conventional name for the tools that expect it.

### The caller/callee secret contract has two sides

An explicit `secrets:` mapping on a caller is valid only if **every key is declared** in the
callee's `on.workflow_call.secrets`. A mapping key the callee does not declare is a load
rejection too. Verify both files together before pushing, not the caller alone.

### Local YAML validation traps

- **`actionlint` passing is not proof GitHub will load it.** actionlint does not enforce the
  reserved-secret-name rule, so a clean lint run can still be a `startup_failure`. Only a real
  run (0 jobs vs real jobs) or the `output.title` annotation proves load success.
- **PyYAML parses `on:` as the boolean key `True`, not the string `'on'`.** `doc['on']`/`doc.get('on')`
  raises `KeyError` / returns nothing even though the file's `on:` block is correct — look up
  `doc.get(True) or doc.get('on')` before concluding the top level is malformed. The `sed`/`grep`
  view of the same file shows `on:` at its line; that contradiction is the PyYAML normalisation,
  not corruption.

### `mergeable=false` / `ms=dirty` with no merge ref can be the SAME load failure

When GitHub cannot compile a called workflow it also cannot build the merge ref: `mergeable`
reads false, `mergeable_state` is `dirty`, `merge_commit_sha` is null and no runs register. Do
not chase that as a merge conflict — run `git merge-tree` against the live `origin/main`; a clean
merge-tree plus 0 check-runs is the load rejection, and the fix is the secret-contract repair,
not a rebase.
