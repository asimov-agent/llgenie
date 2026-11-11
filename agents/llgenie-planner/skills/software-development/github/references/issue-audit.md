# Auditing open issues: still real, already done, or stale

Use when asked to go over the open issues of a busy repo and decide implement-vs-close. The failure
mode to avoid is closing on the issue's own wording ("this is broken") long after the code changed,
and equally the reverse: leaving an issue open because a merged PR merely *mentioned* it.

## Procedure

1. **Snapshot the board** with the age and labels, not just titles:

   ```bash
   gh issue list --repo <owner>/<repo> --state open --limit 200 \
     --json number,title,labels,createdAt --jq '.[] | "#\(.number) [\(.labels|map(.name)|join(","))] \(.createdAt[0:10]) \(.title)"'
   ```

2. **Find what already merged against each issue** — the timeline endpoint, not a text search, because
   it carries the PR's state and merge time:

   ```bash
   gh api repos/<owner>/<repo>/issues/<n>/timeline --paginate \
     --jq '[.[] | select(.event == "cross-referenced") | .source.issue
            | {num: .number, state: .state, merged: (.pull_request.merged_at // ""), title: .title}]'
   ```

   A merged reference is a *lead*, not a verdict.

3. **Verify the claim against the code, not the issue text.** Each issue names its evidence — a file,
   a target, a symbol, a command. Re-run that exact probe: `make -n <target>`, the gate itself, a grep
   for the symbol, `python3 scripts/<x>.py <subcmd>`. Record the literal output; that line is what the
   closing comment quotes.

4. **Sort into three buckets** and only act on the first two:

   | bucket | action |
   |---|---|
   | the probe no longer reproduces / the gate now exists | close, comment with the measured line |
   | the failure is real *and* the fix is small and in scope | open a PR (one issue per PR) |
   | real, but a feature/epic or needs design | leave open, state what was verified |

5. **Report coverage honestly.** Say how many issues were verified in depth out of the total, and list
   the remaining ones by cluster. Claiming "reviewed all N" after probing a third of them is the one
   thing that makes the audit worthless.

## Closing an issue: the comment carries the proof

Quote the command and its output, or the file and line that now implements it. "Implemented" alone
forces the next reader to redo the work.

```
Implemented: `make check-docs` (`scripts/check_docs.py`, run by `ci-unit`) fails when a user-facing
`##` target is not named in README.md … (`Makefile:799`). Verified on current `main`.
```

Never close an issue a still-open PR implements — the PR's `closes #n` is the only honest state change
there. Never close one whose only evidence is a merged PR *referencing* it; check the PR actually did
the work.

## Auto-filed failure issues go stale — treat them as perishable

Bots that file one issue per failed run ("CI / <job> failed") accumulate duplicates of failures that
were fixed days later. Before closing or implementing one:

1. read the run and head sha it names from its body;
2. check the **latest run of the same workflow on the default branch**, not that old run:

   ```bash
   gh run list --repo <owner>/<repo> --branch <default> --event push --limit 1 --json databaseId --jq '.[0].databaseId'
   gh run view <id> --repo <owner>/<repo> --json jobs \
     --jq '.jobs[] | select(.name|test("<job pattern>")) | "\(.conclusion)\t\(.name)"'
   ```

3. same job now `success` → close as stale and say which run proves it; still red → it is a real
   defect and needs its own PR (and the duplicate issues should collapse into one).

   Read the job's STEPS, not just its conclusion: a leg that skips a stage by verdict (a bot that
   triaged `refine` never runs `implement`) goes green without ever executing the gate the tracker is
   about. `gh run view <id> --json jobs --jq '.jobs[].steps[]|"\(.conclusion) \(.name)"'` and require
   `success` on the named failing step before calling a tracker superseded.

## Deduplicate before adding

Two reactor issues naming the same job are one defect. Close the later one as a duplicate pointing at
whichever the PR closes, so the linkage stays single.
