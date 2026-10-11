# fix-engine-bump-allow-skill — proposal

Issue: [#127](https://github.com/asimov-agent/llgenie/issues/127)

## Why

The second live `engine-bump` run (38110707179, after #128 merged) got past
make's directory line and then failed every bump job on the pin edit itself:

```
[engine-bump] regen changed a non-engine file: skills/engines/llama.cpp/SKILL.md
```

The guard allowed only `containers/engines/params/<id>.json` and
`containers/engines/dockerfiles/<id>/`. A bump's whole point is to edit
`skills/engines/<id>/SKILL.md` (pinned/ref/version/verified plus applied
findings). That file is not a stray change.

## What Changes

- `_regen_guard` allows `skills/engines/<id>/SKILL.md` for the bumped engine.
- A change to any other path, including another engine's skill or params, still
  fails the job.

## Out of scope

- Merging bump PRs.
- What the extractors derive.
