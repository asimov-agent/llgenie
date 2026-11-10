# `check-pr-acceptance` — repairing a body-tick red

## It reads the ISSUE, never the PR body

`[check-pr-acceptance] N violation(s)` is almost never a tree defect. `acceptance_verdict()` reads the
**linked issue's** `## Acceptance criteria`, so a bot PR whose own body ticks everything still reds while the
issue it closes has `- [ ]` rows. The evidence quoted in the log (`measured text: …`) is the ISSUE's line, not
the PR's — read it there before editing anything.

Two remedies, and only these two:

1. **tick the row on the ISSUE** with `(proven: <command> rc=<n> <sha>)` or `(proven: run=<id>)`.
   - the bare form `guard run 42444811286` is REJECTED: `RUN_ID` is `\brun\s*=\s*\d+`, so keep the id and
     spell it `run=<id>`;
   - the command form needs BOTH `rc=<n>` and a 7-40 hex sha (`_is_provable_tick`): a `cmp`/hash with no
     `rc=`, or an `rc=` with no sha, is not evidence;
   - the marker must sit at end of the bullet line (`PROVEN_MARKER` is anchored), and an old
     `- unproven: 1. …` bullet left by a previous write-back must be dropped when that item is now proven.
2. **name it out of scope** in the PR body under `## Not covered` beside a linked `#<n>`
   (`_declared_out_of_scope` matches the criterion's first three normalised words). Never mark a
   genuinely-done criterion out of scope to go green, and never tick one you did not measure.

## The `· N proven-awaiting-writer` counter is the VERDICT trail, never `## Not covered`

`render()` prints `{blocking} violation(s) · {pending} proven-awaiting-writer`. The second number is fed
ONLY by `acceptance_verdict`'s `if verdict:` branch (a `bot-verdict` APPROVE marker at the exact current
head — `verdict_evidence` → `verdict_for_head`). A `## Not covered` exemption does NOT move a criterion
into `proven-awaiting-writer`: line 276 `continue`s it out of findings entirely (it counts for nothing in
either bucket — issue #1792's exemption, orthogonal to #2187's three states). So a board reading
`0 proven-awaiting-writer` beside a dropped violation count is CORRECT: the exemption worked (violations
fell), and `proven-awaiting-writer` is 0 because the PR has no approve verdict trail. A `## Not covered`
bullet that ends without a linked `#<n>` is not countable at all — `OUT_OF_SCOPE = ^-.*\s*#\d+\s*$`
requires the `#N` at line end, so those criteria are still held red (a bare claim is an empty gate,
measured #2183). Don't chase "the counter ignores the form" until you have quoted which predicate feeds
`pending` (#2244).

## Measure first, then prove the repair locally

- Run the exact command/module you are about to cite, at the PR's real head, and put THAT sha in the marker.
  Never invent a run id, an rc, or a sha.
- Pre-check without touching GitHub:
  `check_pr_acceptance.acceptance_verdict(<new issue text>, <live PR body>, <issue>)` must return `[]` for
  both. Do this for the PR body edit too — an added `- [x]` can create a `claim-exceeds` finding when its first
  word matches an issue row that is still `- [ ]`, so fix the ISSUE rather than leaving PR ticks over an
  unticked issue.
- Post-check against the LIVE artifacts (this is the read CI does):
  `python3 scripts/check_pr_acceptance.py check --body-file <body> --base origin/main --rev <head>` → `OK`, rc=0.

## Making CI re-evaluate without a push

`gh pr edit --body-file` and `gh issue edit --body-file` do NOT trigger a workflow run. The gate reads the live
body + issue at dispatch time, so `gh run rerun <run-id> --failed` re-evaluates it in the SAME run id and comes
back green with no branch push.

A `--failed` rerun also re-runs the jobs that were merely SKIPPED behind the red — which is how the first real
`linux / unit` verdict at that head appears. Expect it to red on `check-pr-base` when `main` advanced after the
branch was rebased: that red is legitimate (a behind branch must be rebased) and belongs to the rebase lane, so
report it with the log line and route it there; its "foreign commits" wording for a merely-behind branch is
issue #2138. `ci-verdict` stays red until the judged jobs are green — re-judge only then, never to clear a red.

## Host test runs without a container

`tests/conftest.py` imports `scripts.llgenie_serve` (needs `gguf`+`numpy`), so plain `python3 -m pytest` exits 2
with no output at all. A throwaway venv with exactly those imports runs the module in seconds:

```bash
uv run --with pytest --with 'gguf==0.19.0' --with numpy \
  python -m pytest tests/<module>.py -q -p no:cacheprovider
```

`-p no:cacheprovider` sidesteps a `Permission denied` on a root-owned `.pytest_cache`. `make test-unit` /
`make lint` DO work on this host (docker + `llgenie/test:latest` are reachable), so item-7-style "green at the
fixing head" claims can be measured for real: `make test-unit` printed `3258 passed, 13135 deselected` in 9m.
