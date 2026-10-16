# A workflow GitHub refused, and the gate that stops the next one (#330, #329)

Implemented by PR [#331](https://github.com/asimov-agent/llgenie/pull/331) (issue #330).

## Why

`.github/workflows/engine-bump-rebase.yml` never started. Every push to `main` touching
`.github/workflows/**` landed a red, **0-job** run for it:

| run id | head sha | event | conclusion | jobs |
|---|---|---|---|---|
| 38850302335 | `ed75b870` | push | failure | 0 |
| 38850145191 | `c9fc82c4` | push | failure | 0 |
| 38849945773 | `38d54aa1` | push | failure | 0 |
| 38844778241 | `e2715093` | push | failure | 0 |

Signature: `name` = the **file path**, `jobs` `total_count` 0, `gh run view --log-failed` → `log not
found`. That is a GitHub startup failure — the file was refused before any job existed.

The cause was one comment inside the `rebase` job's `run: |` block:

```yaml
          # folded into one `${{ ... }}` so the mode this run took is readable in the log.
```

A `#` line inside a block scalar is **script text, not a YAML comment**, so GitHub's expression parser
read `${{ ... }}`, could not parse `...`, and refused the whole file. actionlint names it exactly:

```
.github/workflows/engine-bump-rebase.yml:87:361: unexpected token "." while parsing variable access,
function call, null, bool, int, float or string. expecting "IDENT", "(", "INTEGER", "FLOAT", "STRING" [expression]
```

`yaml.safe_load` accepts the file — PyYAML has no notion of `${{ }}` — so no review, test or gate saw it.
`git grep -n '\${{ *\.\.\.' -- '*.yml'` found exactly **1** hit repo-wide.

## What landed

- **`.github/workflows/engine-bump-rebase.yml`** — the comment no longer writes expression syntax, and it
  says why it must not (a `${{ ... }}` in a `run:` comment is parsed; an unparseable one refuses the file).
  The dry/real mode stays fully readable from the `if`/`echo` branch, which was already the real signal.
  `actionlint` is clean on the file and both `run:` blocks still pass `bash -n`.
- **`scripts/check_workflows.py`** (new, stdlib only) — `check` / `report`. `check` reads every YAML file
  (`git ls-files`, or a walk when the tree is not its own checkout) and fails on
  1. a `${{ ... }}` that does not parse — a real recursive-descent parser over GitHub's expression grammar
     (`|| && == != <= >= < > ! - + * / %`, property access `.x` / `.*` / `[...]`, function calls, numbers,
     single-quoted strings, `true`/`false`/`null`);
  2. a YAML file without a trailing newline (the repo's linefeed lint spec);
  3. a `.github/workflows/*.yml` with no top-level `name:`.
- **`make check-workflows`** / **`make workflows-report`**, the first wired into `ci-unit` after
  `check-pr-hygiene`, both in `.PHONY`.
- **`tests/test_workflows_valid.py`** (new, in `make test-unit`, which `ci.yml` runs): 11 cases — the
  pre-fix line is caught with `unexpected token '.'`, the 14 expression forms this repo uses are not false
  positives, the missing newline and missing `name:` rules, the every-YAML-file scope, the strict
  duplicate-key loader, and the exit-code contract.
- **`AGENTS.md`** — a durable section: a `#` inside `run:` is script text, `yaml.safe_load` does not save
  you, a 0-job run named after the path is a startup failure, and `make check-workflows` is the gate.
- **`README.md`** — the two targets in the command list plus the rule.
- **`#329`** — actionlint's shellcheck findings (SC2086 / SC2016 / SC2129) in five other workflows are
  lint debt GitHub accepts; filed separately and named in the PR's `Not covered`.

## Verification

- **The gate fires on the pre-fix tree and passes on the fixed one:** on `origin/main`'s
  `engine-bump-rebase.yml` it reports exactly one violation
  (`workflow-expression`, line 92, `unexpected token '.'`); on the fixed tree `make check-workflows` exits
  **0** and `actionlint` is clean.
- **No false positives:** all 70 distinct `${{ ... }}` forms in the repository parse (the only failure is
  the one being fixed).
- **`tests/test_workflows_valid.py`: 11 passed** in `llgenie/test:latest`
  (`docker run --rm -v "$PWD":/repo:ro … -m pytest tests/test_workflows_valid.py --noconftest`).
- `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene`, `make check-dispatch-forms`,
  `make openspec-validate NAME=check-workflows`.

## Note

The gate validates the class that makes GitHub REFUSE a file; it does not re-run actionlint's shellcheck
rules, which GitHub accepts (that is #329). The make gate is stdlib only so `ci-unit` can run it on the
host on Linux and macOS alike; the checks that need a YAML library — a strict parse with no duplicate
keys, which GitHub refuses and PyYAML hides — live in the unit test instead.
