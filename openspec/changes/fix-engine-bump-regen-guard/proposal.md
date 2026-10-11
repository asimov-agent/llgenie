# fix-engine-bump-regen-guard — proposal

Issue: [#107](https://github.com/asimov-agent/llgenie/issues/107)

## Why

The first live `engine-bump` run (38109392303, after #126 merged) planned six
engines and every bump job failed:

```
[engine-bump] regen changed a non-engine file: make[1]: Entering directory '/home/runner/work/llgenie/llgenie'
```

`_regen_guard` treated every non-empty line of `make generate-engine-params`
stdout as a changed path. GNU make prints `make[1]: Entering directory ...`
on stdout, so the guard rejected a clean regen and no bump PR opened.

## What Changes

- `_regen_guard` reads `git status --porcelain` after the regen, not make's stdout.
- The regen writes only the bumped engine (`make generate-engine-params ENGINE=<id>`).
  Rewriting every engine's params would fail the guard, so no bump PR would open.
- A make directory line is never a changed path.
- A change outside `containers/engines/params/<id>.json` and
  `containers/engines/dockerfiles/<id>/` still fails the job.

## Out of scope

- Merging bump PRs.
- Changing what the extractors derive.
