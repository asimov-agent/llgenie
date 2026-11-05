# OpenSpec change-first: every code change carries its own change dir

## The rule
Every code change in the repo must be accompanied by an OpenSpec change under
`openspec/changes/<name>/`. AGENTS.md makes this mandatory and *change-first*
(write the change with the code, not after). An implementer PR that touches code
but adds no `openspec/` file is "openspec-empty" and is a legitimate
`do-not-merge` whose remedy is exactly "carry your own OpenSpec change".

## CI validates but does NOT enforce presence
`linux / openspec` runs `make ci-openspec`, which validates every active change
and exits 0. On an openspec-empty PR it passes because there is nothing to
validate — absence is not a red. So a green `linux / openspec` is NOT proof your
PR carries a change: verify the directory exists in the head tree yourself with
`git ls-tree -r <head> -- openspec/changes/<name>/`. The gate that reds an
implementing PR for a missing/unnamed openspec change is a separate CI-pipeline
concern, not this leg.

## Scaffold then AUTHOR the files
`make openspec-new <name>` (dockerised `openspec` scaffold) creates only
`.openspec.yaml`. You must author the real content:
- `openspec/changes/<name>/proposal.md` — why + what changes
- `openspec/changes/<name>/tasks.md` — checklist, all `- [x]` when done
- `openspec/changes/<name>/specs/<name>/spec.md` — the requirement delta
Validate before pushing: `make openspec-validate` and `make ci-openspec` both
rc=0. Re-add trailing newlines (write_file drops them) so check-docs stays green.

## Docker scaffold writes as root
A dockerised scaffold/validate writes files owned by root; the next `write_file`
into the change dir fails `Permission denied`. `sudo chown -R $USER:` the change
dir before editing.

## Clear the do-not-merge yourself when its remedy lands
A `do-not-merge` placed for openspec-empty is removable once the change is in
the branch and CI validates it: amend/push the change, then
`gh pr edit <n> --repo <o>/<r> --remove-label do-not-merge`, and re-run the
`holds` check (the failed run predates the removal). Confirm `check-holds` reads
0 held PRs and `gh pr checks <n>` shows `holds pass` before reporting green.
