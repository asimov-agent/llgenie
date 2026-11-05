# Running gates and CI probes without burning the turn

Every gate here (`make check-docs`, `make check-architecture-census`, `make test-unit`, the
`gh` queries that read a PR or a run) is slow enough that running it twice for one fact is a
real cost, and noisy enough that dumping its full output into the transcript hides the one
line that matters.

## One run per fact, captured once

- Run the gate **once** with `capture_output=True` (or the terminal tool with no pipe) and
  print only the return code plus the trailing lines that carry the verdict. Do not re-run it
  because the first print was truncated — the captured string is already in a variable; slice
  it.
- Piping `make … | tail -40` makes the shell's exit status the pipe's, not the gate's. Never
  conclude green/red from a piped tail; the honest rc comes from an unpiped run.
- When the artifact is a background log (`make test-unit > /tmp/x.log`), poll with a single
  call printing size + last two lines, and stop polling by hand once a notify-on-complete
  background job owns the wait. Repeated identical polls add nothing.

## Batch the independent reads

"Does the commit carry the fragment", "is the branch on both remotes", "what is the PR head"
are three independent facts: gather them in ONE `execute_code` call and print a compact
key=value line, not one call per fact. The failure mode this prevents is dozens of
near-identical probes whose outputs drown the reasoning.

## Reading `gh` output

- `gh pr view <branch> --json number --jq .number` works, as does
  `gh api 'repos/<org>/<repo>/pulls?state=open' --jq '.[] | ...'`. A `422 "base wasn't
  supplied"` almost always means the field flags were swallowed by shell quoting, not that the
  API changed — re-issue from a plain argv list instead of a quoted shell string.
- `gh pr create` exiting non-zero with `a pull request for branch … already exists` is a
  SUCCESS signal: the PR exists, so read its number rather than retrying the create.
- Verify `mergeable` and `head.sha` by API read-back after any push. A push that succeeded and
  a PR that points at the new head are two different facts.

## Keep each call's payload SHORT — a big command is dropped before it runs

A terminal command that is too LONG is dropped at the transport layer **before it executes**.
The failure reads like a timeout ("tool call was too large … stream timed out before it could be
delivered"), but no side effect happened, so the retry is safe and the fix is to shrink the call,
not to rerun it verbatim. A multi-line `for`/`while` poll loop with an inline multi-clause
`--jq` pipeline is the classic offender: it can exceed the per-call argument cap (~8K tokens) and
never reach the shell. The tell is an instruction to break the content into smaller calls, not an
exit code. Prefer single-shot queries — `gh run list --commit <sha> --json status,conclusion`,
then a small `gh pr checks <n>` — and a couple of small calls over one giant embedded script;
never paste a long inline loop into one call.

## When the capture comes back empty, repeated or mangled

An empty or obviously stale stdout is a fact about the RENDERER, not about the command. The
process ran: its exit code, its file writes and its remote effects are all real. Never re-run a
mutating command (push, `gh pr edit`, `gh pr create`, a gate that rewrites `CHANGES.md`) to "fix"
a blank render — that is how a second PR or a second force-push appears.

- **Blank/`""` output:** write the result to a file in the same call and read it back with
  `read_file`; a file's bytes do not depend on the transcript renderer. `search_files` on the
  saved file is the cheapest way to pull just the verdict lines out of several KB.
- **Stale or repeated output (same lines twice, a reply to a call you did not just make):**
  prepend a unique marker to the command (`echo PROBE_A1; …`) and confirm it appears exactly once.
  Identical marker in two consecutive results means the second result is a replay, not a new run.
- **Mangled output from `%`-format git commands:** `git log --format='%h %p %s'` interpolated into a
  `%`-formatted shell/printf string has its `%h`/`%p` eaten by the outer format. Put `--format` in a
  plain argv command (or use `git rev-parse`/`git merge-base` per fact) instead of formatting the
  whole command string.
- When several probes in one turn all come back blank, stop probing and re-establish one fact at a
  time in a single call that writes to a file — do not spiral into dozens of near-identical calls.

## Completion is the pushed-head CI verdict, not your local `make` gates
`make lint`, `make check-docs` and the four `bot-preflight` body gates passing in your worktree
prove the TREE; they do not prove the PR. CI runs its own matrix at the pushed head, and its long
pole (`ci-images`/`scanner-images`, `linux / unit` ~10-12 min) is what a reviewer and the merge
gate actually read. Reporting "done/green" while the pushed-head `push` run is still
`in_progress`/`queued` is a claim about your machine, not the branch. Completion = the run set at
`headSha == your head` all `completed/success` AND `gh pr checks <n>` showing zero `pending`/`fail`.
Poll the runs to conclusion (`gh run view <id> --json status,conclusion`), quote the run ids, then
report. Local gates green is necessary, never sufficient — and never call a PR reviewable or
mergeable while a heavyweight row is unread or queued.

## Force-push verification

After an amend + `git push --force-with-lease <remote> <branch>`, prove it landed by comparing
`git ls-remote <remote> refs/heads/<branch>` with local `git rev-parse HEAD` for **every**
remote the lane pushes to (fork and origin). Both matching is the only proof; the push's exit
0 is not.
