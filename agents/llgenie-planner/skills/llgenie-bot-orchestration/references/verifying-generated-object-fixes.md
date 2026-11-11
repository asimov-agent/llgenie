# Verifying a "done" on a generated-file fix

A lane's report of "done" on a fix to a generated artifact is a claim; the generated object at
the branch tip is the evidence. This is the failure mode to expect and the check that settles it.

## The trap: references updated, object untouched

When a fix targets a GENERATED file — a Dockerfile `FROM`/base-image tag, a rendered config, an
emitted manifest, a pinned `ref` in a params JSON — a lane can update every *reference* to the new
value while leaving the actual object at the old one:

- the agent-wiki / docs note rewritten to say the new version,
- the params JSON `ref` bumped,
- the unit-test assertion bumped to expect the new value,

…and the real generated file (the `FROM lmsysorg/sglang:vX` line, the rendered block) still carries
the old value. Three pointers to the new state, the object itself untouched.

**Tell in the diff:** the pointer edits show up as `+`/`-` on docs/params/test, but there is *no*
`+`/`-` line on the real object. If the diff never touches the generated file, the fix never landed
there regardless of what the report says.

**Self-inflicted red:** when the lane also bumped the test's expected value, the changed assertion
then contradicts its own tree and goes red *deterministically* on that assertion — not a race, not a
flake. A green-looking report and a PR whose own new test must fail is the signature.

## The check (settle it in one read)

Read the object at the head, not the diff and not the assert:

```bash
h=$(gh pr view <n> --json headRefOid --jq '.headRefOid')
gh api "repos/<owner>/<repo>/contents/<path>?ref=$h" --jq '.content' | base64 -d | grep -E '<needle>'
```

Then count old-vs-new **at the tip** — expect `new=N` and `old=0`. Any `old>0` in the actual object
means the drift is not fixed. (A count of removed `-` lines in the diff is expected and irrelevant —
count at the tip, not in the diff.)

## What to dispatch

If the tree still carries the old value: the fix is the real object edit plus re-derivation
(`make generate-*` when the file is generated from a source of truth), on the lane's own branch —
not a description of it, and not handed to another lane. Confirm the hygiene portions that *are*
correct so the lane knows what to keep, and post the evidence on the PR (read it back) so the board
carries the correction, then DM the lane with the same evidence.
