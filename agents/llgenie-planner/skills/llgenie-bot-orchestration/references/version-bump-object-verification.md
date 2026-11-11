# Verifying a version-bump fix: the object, not the assertions about it

A lane can "fix" a version-drift finding by editing everything *around* the object while the
**actual generated object stays on the old version**. The report then reads "three reference
sites updated, drift fixed" and looks green-adjacent — but the thing the finding named is
untouched, and the edited assert now contradicts its own tree, so `linux/unit` reds on the
changed assertion itself. This is a deterministic self-inflicted red, not a race.

Worked case: the sglang base-image drift. The lane bumped the params `ref`/`base`, the wiki
note, and the unit test's expected tag to `v0.5.23` — but `containers/engines/dockerfiles/
sglang/Dockerfile.cuda` still had `FROM lmsysorg/sglang:v0.5.22`. The finding was about the
`FROM` line; that was the one line the diff never touched.

## Check the object, never the diff

```bash
h=$(gh pr view <n> --json headRefOid --jq .headRefOid)
gh api "repos/<org>/<repo>/contents/<path>?ref=$h" --jq .content | base64 -d \
  | grep -E 'FROM <image>:v'      # or the version pin line for a params JSON
```

A count of the old tag at the tip (`... | grep -c 'v0.5.22'`) returning 1 while the new tag
returns 0 is the proof the object is unchanged, regardless of how many references the report
claims to have updated. Reading the PR *diff* is not enough: `-v0.5.22` lines can be the wiki
note and the assert, so a "3 old / 3 new" count looks like a clean swap while the real object
was never in the diff.

## Generated files are derived — check the regenerate step ran

Dockerfiles and params JSON are `GENERATED` from a source skill/params (`make
generate-engine-params`). If the params carry the new version but the generated file still
shows the old, the regenerate step was skipped. Don't hand-edit the generated file in
isolation; land the regenerate so params and object agree.

## "All N sites" can be honest when one site has nothing to bump

Not every generated file carries the line. The sglang `.rocm` Dockerfile compiles from a bare
base and has no `FROM lmsysorg` line at all (only the prebuilt `.cuda` starts from the official
image). So a lane saying "bumped all four reference sites" is accurate when one of the four is
`SKILL.md`/params and the `.rocm` legitimately has no such tag — verify each named site
actually exists before calling the claim inflated.
