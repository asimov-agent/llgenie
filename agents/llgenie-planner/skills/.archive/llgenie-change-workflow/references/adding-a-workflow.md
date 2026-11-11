# Adding (or editing) a GitHub workflow in llgenie

The repo pins its pipeline conventions with tests, not prose. A workflow file that reads correctly can
still fail four different `make test-unit` suites, and each failure is a different contract. Run the
four files below after ANY workflow edit — they are seconds each — instead of discovering it in the
~10-minute full suite (or in `ci-unit` on the PR).

```bash
~/llama-gguf-tools/.venv/bin/pytest -q -p no:cacheprovider \
  tests/test_workflow_guards.py tests/test_bot_pipeline_isolation.py \
  tests/test_code_review.py tests/test_secret_output.py \
  tests/test_renovate_config.py        # when the edit touches a config a test already reads
make -s check-workflows check-dispatch-forms check-actions
```

## 1. The guard (tests/test_workflow_guards.py)

Every workflow carrying `workflow_dispatch` needs the **byte-identical** guard: a `guard` job whose
single step is named `Owner / collaborator trigger guard` with exactly the env keys
(`ACTOR`, `TRIGGER`, `OWNER`, `REPO`, `HEAD_REPO`, `GH_TOKEN: ${{ github.token }}`) and exactly the
shared `run:` body — copy it verbatim from an existing bot (`security-scan.yml`, `engine-bump.yml`).
The guarded job must then declare `needs: [guard]`; a guard job nothing needs is a failure. A step-level
guard is only allowed when that job's `if:` is exactly
`github.event_name == 'workflow_dispatch'`.

## 2. Cron slot isolation (tests/test_bot_pipeline_isolation.py)

No two bots may own the same `(minute, weekday)` slot, and a daily/weekly bot may not reuse a minute an
every-hour bot reserves on all seven days. Read what is taken, then pick a free **odd** minute
(GitHub drops many top-of-hour/even-minute runs):

```bash
grep -rn 'cron:' .github/workflows/*.yml
```

Every-hour crons (`M * * * *`) reserve their minute permanently; `M */6 * * *` reserves it too. Move the
header's claimed `HH:MM UTC` with the cron in the same edit — `check-dispatch-forms` compares them.

## 3. No inline script calls (tests/test_code_review.py)

A step must reach repo logic through a make target, never `python3 scripts/<x>.py` in the `run:` block.
The target usually already exists: `make require-env KEYS="BUMP_TOKEN"` for the credential guard,
`make -s <report>` for generated output. If there is no target, add one, wire it in `.PHONY` and in the
job that should run it — the check is on the real tree, so it fails on the file you just wrote.

## 4. Secrets roster (tests/test_secret_output.py)

Every `secrets.<NAME>` a workflow reads must appear in `scripts/check_secret_output.py::SECRET_VARS`
(the redactor's one list). Introducing a new secret name therefore means either adding it there (and to
the redaction tests' expectations) or reusing an existing one — prefer reusing `BUMP_TOKEN` for a bot
that only pushes branches and opens PRs. `<A> || <B>` in a `token:`/`env:` value names both, so the
fallback form fails the roster too.

## 5. Pinned actions (make check-actions)

Every `uses:` is `<owner>/<repo>@<40-hex sha>`. Resolve a new action's SHA from the release tag, not from
memory:

```bash
gh api repos/<owner>/<repo>/releases/latest --jq .tag_name
gh api repos/<owner>/<repo>/commits/<tag> --jq .sha
```

## 6. Dispatch form + docs table

`check-dispatch-forms` also wants the `name:` shape, the header keys, a documented input or
`# dispatch: no inputs — <reason>`, and a regenerated `docs/BOTS.md` table (paste with
`make -s dispatch-forms-report`). See the pitfall in SKILL.md.

## Why one workflow is four suites

These contracts were each added after a distinct incident, so they live in four files with four
fixtures. Nothing in `.github/workflows/` is checked by a single gate, and the full `make test-unit` is
the only run that exercises all of them at once — budget for it whenever a workflow changes, even when
the change is "only" YAML.
