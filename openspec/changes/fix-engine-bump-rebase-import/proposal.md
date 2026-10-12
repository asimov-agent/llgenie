# fix-engine-bump-rebase-import — proposal

Issue: [#214](https://github.com/asimov-agent/llgenie/issues/214)

## Why

Run [38318141627](https://github.com/asimov-agent/llgenie/actions/runs/38318141627)
is a `workflow_dispatch` of `engine-bump-rebase` on `main` at `9b8d536`. The
guard passed. The rebase job failed:

```
File "scripts/engine_bump_rebase.py", line 29, in <module>
    from scripts.engine_bump_sync import (
ModuleNotFoundError: No module named 'scripts'
```

The workflow runs `python3 scripts/engine_bump_rebase.py`. That puts
`scripts/` on `sys.path`, so `import scripts` does not resolve. Pytest puts
the repo root on `sys.path`, so the existing unit tests stay green.

## What Changes

- The entrypoint adds the repo root to `sys.path` before importing
  `scripts.engine_bump_sync`.
- The workflow command stays `python3 scripts/engine_bump_rebase.py`.
- A test runs that file and fails if the import is missing.

## Out of scope

- Changing which PRs are rebased.
- Re-dispatching the workflow. That happens after this lands on `main`.
