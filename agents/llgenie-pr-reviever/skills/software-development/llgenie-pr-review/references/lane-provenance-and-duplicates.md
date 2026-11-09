# Lane provenance and duplicate comments

## Why

All fleet bot lanes authenticate as the same GitHub user (`andyholst`). `user.login` therefore says nothing about which lane wrote a comment. Provenance lives in the body's first line:

`BOT llgenie-<lane> · #<id> · branch <ref> · since <hh:mmZ> · blocked on … · next …`

## Rule

- Attribute a comment by its `BOT <lane>` prefix, never by `user.login`.
- An `andyholst` comment naming another lane (`BOT llgenie-ci-pipelines-maintainer`, `BOT llgenie-planner`, `BOT llgenie-implementer`, …) is that lane's record. It is **not** a duplicate of yours and must not be deleted as one.
- Only a comment whose prefix is your own lane (`BOT llgenie-pr-reviever`) and which repeats your verdict/write-back text is a replay duplicate.

## Reading the comment surface

Use `gh api` with `--jq` directly; do not wrap it in a throwaway python script. The `subprocess.run(["gh"] + args)` idiom breaks when `args` is a tuple (`can only concatenate list (not "tuple")`) — prefer a straight `gh api … --jq` pipeline:

```
gh api repos/OWNER/REPO/issues/<n>/comments --paginate \
  --jq '.[] | {id, at:.created_at, lane:(.body|split("\u00b7")[0]), body:.body[:80]}'
```

Inline PR review comments are a separate surface (`/pulls/<n>/comments`); the issue + PR conversation is `/issues/<n>/comments`.

## Distinguishing replay duplicates

A batched terminal command set can replay, re-posting the same `gh comment` / `gh pr review`. After a suspicious replay, list the surface and keep the single comment your `(proven: comment=<id>)` marker pins; delete only same-lane repeats. Verify on the wire (`gh api`) before re-running anything, so you never re-post while confirming.
