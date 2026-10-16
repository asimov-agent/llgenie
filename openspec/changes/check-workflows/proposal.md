# Every workflow file is validated on every run — a rejected file can no longer ship silently

## Why

`main` has a workflow GitHub **refuses to start**. Every push touching `.github/workflows/**` lands a red,
**0-job** run for `.github/workflows/engine-bump-rebase.yml` (`38850302335`, `38850145191`, `38849945773`,
`38844778241`, all `event=push`, `jobs=0`, `name` = the file PATH, `gh run view --log-failed` → `log not
found`).

The cause is one line of the `rebase` job's `run: |` block:

```yaml
          # folded into one `${{ ... }}` so the mode this run took is readable in the log.
```

Inside a `run: |` block scalar a `#` line is **script text, not a YAML comment**, so GitHub's expression
parser reads `${{ ... }}`, cannot parse `...`, and refuses the whole file:

```
.github/workflows/engine-bump-rebase.yml:87:361: unexpected token "." while parsing variable access,
function call, null, bool, int, float or string. expecting "IDENT", "(", "INTEGER", "FLOAT", "STRING" [expression]
```

`yaml.safe_load` accepts the file — PyYAML has no notion of `${{ }}` — so no review, test or gate saw it.
`git grep -n '\${{ *\.\.\.' -- '*.yml'` finds exactly **1** hit repo-wide, so this is not a class already
half-fixed; it is a class nothing checks at all.

## What changes

- **`.github/workflows/engine-bump-rebase.yml`** — the comment is reworded so no literal `${{ ... }}` remains.
  The mode is already stated unambiguously by the `if [ "${DRY_INPUT}" = "true" ]` branch and its two `echo`s,
  so the sentence only has to stop naming the expression syntax.
- **`scripts/check_workflows.py`** (new, stdlib only) — `check` / `report`. `check` reads every tracked
  `.github/workflows/*.yml` and fails on
  - a `${{ ... }}` expression that does not parse (the class GitHub rejects a whole file for),
  - a file that does not end with a newline (the repo's own linefeed lint spec),
  - a file with no top-level `name:` (which is what makes a startup failure present itself as a path).
- **`make check-workflows`** / **`make workflows-report`**, the first wired into `ci-unit` next to
  `check-docs` / `check-pr-hygiene`, so it runs on every Linux and macOS CI run.
- **`tests/test_workflows_valid.py`** (new, wired into `make test-unit`, which `ci.yml` runs) — the guard
  fires on the pre-fix text, passes on this repo, and every workflow file parses as strict YAML with no
  duplicate keys (a check only PyYAML can make, run where PyYAML exists).
- **`AGENTS.md`** — the rule, so the next agent knows a `#` inside `run:` is script text and that a rejected
  file shows up as a 0-job run named after its path.

## Impact

A workflow file GitHub would refuse fails `ci-unit` before it merges, with the file and the expression named.
The "is main green?" signal stops carrying a red run that no job ever produced, and the fix is visible: the
gate fails on the pre-fix line and passes on the reworded one.

## Not covered

- **#329** — actionlint's shellcheck findings (SC2086 / SC2016 / SC2129) in `ci.yml`, `code-review-bot.yml`,
  `engine-bump.yml`, `issue-bot.yml` and `rebase-bot.yml`. GitHub accepts those files, so they are lint debt
  rather than this defect; they are filed as their own work item and named in the PR's `Not covered`.
