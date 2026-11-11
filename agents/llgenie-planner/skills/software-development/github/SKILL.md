---
name: github
description: "GitHub via gh CLI: PRs, issues, reviews, repos, auth."
version: 2.0.0
author: Ben Barclay (benbarclay), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, gh, git, pull-requests, issues, code-review, repos, auth, ci]
    category: software-development
    related_skills: [codebase-inspection, requesting-code-review]
---

# GitHub

Work GitHub end to end with the `gh` CLI (REST fallback where noted): auth,
issues, the PR lifecycle, issue-to-PR delivery, code review, and repo
management. This skill consolidates six former skills; each workflow lives
complete in its reference file — ALWAYS read the matching reference before
starting that workflow, the body below only routes.

## Routing

| Task | Read first |
|---|---|
| Auth broken / new machine / token or SSH setup / gh login | `references/auth.md` |
| Create, triage, label, assign, close issues | `references/issues.md` |
| Branch, commit, open PR, watch CI, merge | `references/pr-workflow.md` |
| Carry an ISSUE to a verified PR (full delivery loop) | `references/issue-to-pr.md` |
| Review someone's PR: diffs, inline comments, verdict | `references/code-review.md` |
| Clone/create/fork repos, remotes, releases | `references/repo-management.md` |
| Audit CI logs/artifacts for leaked secrets + runner restrictions | `references/ci-secret-leak-audit.md` |
| Build secret-masking into bot/agent workflows (prevention) | `references/ci-secret-masking.md` |
| Let CI merge the PR (auto-merge gates, deferrals, fork heads) | `references/auto-merge-gates.md` |
| Audit open issues: still real, already merged, or stale | `references/issue-audit.md` |
| A red ALARM workflow (sweep, queued-run, freshness) means another pipeline is not delivering | `references/ci-troubleshooting.md` → *An alarm workflow's red is the SIGNAL* |
| A job that "just stops" mid-step / "the download stopped" — run ends `cancelled`, log is `BlobNotFound` | `references/ci-troubleshooting.md` → *A job that "just stops" mid-step* |
| Branch/ref, PR and check endpoints | `references/github-api-cheatsheet.md` |
| A PATCH to `labels`/`assignees` 422s "not an array", or a check-run id 404s under `actions/runs` | `references/github-api-cheatsheet.md` → *Array-valued fields need `--input`* / *check-runs[].id is not a run id* |
| A filtered GET (`actions/runs` etc.) 404s under `gh api -f`, or `gh api repos/<o>/<r>/pulls --state open` errors `unknown flag: --state` — list filters (`state`, `per_page`, `page`) go in the URL query string (`'repos/<o>/<r>/pulls?state=open&per_page=20'`), never as flags | `references/github-api-cheatsheet.md` → *`gh api -f` on a GET endpoint* |
| Harden the supply chain: pin Actions to SHAs, build immutable scanner/tool images, run the pin gate | `references/supply-chain-pinning.md` |

Supporting assets: `scripts/gh-env.sh` + `scripts/git-credential-token.py`
(auth helpers), `templates/` (PR bodies, bug report, feature request),
`references/ci-troubleshooting.md`, `references/ci-secret-leak-audit.md`,
`references/ci-secret-masking.md`,
`scripts/scan-ci-secrets.py` (credential-shape + literal-value scanner),
`references/conventional-commits.md`,
`references/github-api-cheatsheet.md`, `references/review-output-template.md`.

## Core discipline (applies to every workflow)

- Preflight once per session: `gh auth status` — if it fails, go to
  `references/auth.md` before anything else.
- Prefer `gh` over raw REST; drop to `gh api` only for endpoints the
  porcelain lacks (the cheatsheet lists them).
- Never report CI green without checking `gh pr checks` yourself; never
  claim merged without verifying `state,mergedAt`.
- **A run's status is not its jobs' status.** `gh run list --commit <sha>` prints `queued/`
  whenever ONE job is still queued (a scarce macOS runner, a saturated queue) even though twenty
  others finished — some red. Triage from `gh pr checks <n>` and
  `gh run view <run> --json jobs --jq '.jobs[]|select(.conclusion=="failure")'`, and a PR with no
  red line is backlogged, not broken. `gh run rerun <run> --failed` also refuses ("cannot be
  retried") until the whole run completes, so a dependency that is mid-flight blocks the rerun too.
- Triage a red run before writing code: read the failing STEP's own line
  (`gh run view --job <id> --log`, or `gh api repos/<o>/<r>/actions/jobs/<id>/logs
  --allow-escape-sequences` when gh refuses the log for containing terminal escapes),
  then diff it against the most recent GREEN
  run of the same workflow. Get the job ids without guessing: `gh pr view <n> --json
  statusCheckRollup --jq '.statusCheckRollup[]|select(.conclusion=="FAILURE")|{name,detailsUrl}'`
  — the check name maps to the job, and each job's log carries an ISO-8601 timestamp prefix (`…T…Z `) plus ANSI colour, so strip both (`sed -e 's/\x1b\[[0-9;]*m//g'`) and grep for
  `FAIL|Error|assert|Traceback` before reading: the tail of the log is teardown noise and
  the assertion line is usually hundreds of lines above it. For "why is this PR failing?", follow the fixed
  order in `references/ci-troubleshooting.md` → *Answering "why is this PR
  failing?"* (verdicts → failing job logs → guard vs broken test → reproduce in
  a PR-head worktree → group by cause). A sub-minute failure at a `*-check`/`*-pre-flight`
  step is a credential/permission verdict, not a build bug; if a green run
  exists on another branch the fix may already be written — `git log -S` /
  `git branch --contains` / `gh pr list --head <branch>` before re-implementing
  (`references/ci-troubleshooting.md`).
- Read full context before writing: `gh issue view --comments` /
  `gh pr view --comments` — decisions live in threads, not titles.
- **A red PR your change did not cause is a shared-gate defect, not a repair job.** Reproduce the failing
  make target on a clean base; when it is red there too, fix the stale artifact with its own generator
  target (its own `data(...)` commit) and file the gate's design defect as a separate linked issue —
  never weaken the check. Recipe: `references/pr-workflow.md` → *A red PR that its change did not cause*.
- **A board full of red PRs is ONE incident.** Before triaging any single PR, read the whole
  board (`gh pr checks <n>` for every open PR) plus the default branch's last run: identical
  failing cases on branches that touch none of that code mean one cause. Fix that cause as its
  own small PR off the default branch, then rebase the blocked PRs onto it — never paste the
  same lines into each PR, and never ask the user which red to start with.
- **A red alarm/health-check workflow is a SIGNAL, not the failure.** A scheduled sweep-age, queued-run
  or freshness alarm goes red when ANOTHER pipeline stops delivering, and its log names that pipeline's
  newest run. Open the run it names and triage that: the answer to "why is this run failing?" is usually
  two runs away (alarm → failing producer → the producer's own silent step). See
  `references/ci-troubleshooting.md` → *An alarm workflow's red is the SIGNAL*.
- **Prove a remote-state check against the live API, not from the source.** A "branch/PR already exists"
  check can be dead code while every test is green (a stub answering `[]`). Create a throwaway ref with
  `gh api -X POST .../git/refs`, run the real target, read the helper's own return value, DELETE the ref
  — evidence instead of inference (`references/ci-troubleshooting.md` → *throwaway ref*).
- **Reproduce before labelling a red a flake.** Re-run once to separate a genuine flake from a
  product defect, then read the failing line — not the summary. A red whose log shows a product
  assertion is a defect even when the re-run goes green; a red that clears repeatedly with no code
  change is the flake. Concurrency/ordering failures are the real flake candidates.
- **A fork PR's write denial is a permission verdict, not a code defect.** A job that fails only
  because a fork head's token cannot push/package/publish means the write belongs on the base repo's
  merge run — do not "fix" the test or add retries. Say which it is in the triage note.
- **A label passed to `gh issue create` is not evidence the issue is labelled.** On a CI token path
  the create can exit 0 with the label silently dropped (no `labeled` event at all), so a bot-filed
  issue arrives unlabelled and no label-driven bot ever reads it — a green run that routed work to
  nobody. In any automation: create, then apply the label explicitly (`gh issue edit <n> --add-label
  <l>`), then read it back (`gh issue view <n> --json labels`) and fail the step naming the issue when
  it is absent. Repair an existing unlabelled issue the same way instead of skipping it. Recipe:
  `references/issues.md` → *Labels in an automated workflow*.
- **A `gh` porcelain subcommand silently lacks the flag you expect — reach for the dedicated verb, not a flag.** Grounded instances: `gh issue edit` has NO `--state` (reopen/close via `gh issue reopen <n>` / `gh issue close`); `gh issue comment` has NO `--jq` (drop it, or post then read back with `gh issue view --json`); `gh pr merge` has NO `--cancel` — dis-arming an auto-merge is `--disable-auto`. When a flag errors `unknown flag`, check `gh <verb> --help` rather than guessing synonyms; the command that "should" take it usually has a sibling verb that does.
- **Batch reads, serialize writes.** Independent GETs belong in one parallel call; **mutating calls
  (POST/PATCH/DELETE, `gh issue comment`, `gh api -X POST`) must go one per turn.** Parallel tool calls
  execute concurrently and every one lands, so a batch in which each call posts "the" status comment
  posts it N times onto the same issue — the duplicate write corrupts the exact trail the write exists
  to keep, and the cleanup is a second round of mutating calls that each need their own read-back.
  Issue one write, read it back by the id it returned, then issue the next.
- **A write that landed cannot be un-guessed — delete the extras and prove one survives.** When
  duplicates are already on the thread: `gh api -X DELETE repos/<o>/<r>/issues/comments/<id>` for each
  surplus id, then re-list (`?per_page=100`) and assert the intended note appears exactly once and is
  still the newest. Report the accident on the thread rather than silently cleaning it.
- Sweep for duplicates before creating anything:
  `gh pr list --search` / `gh issue list --search`.
- **Measure after a failed create; never blind-retry.** `gh issue create` has no `--json` (passing it
  aborts before any network call) and prints only the new URL — so a non-zero exit can mean "nothing
  created" OR "created, URL lost". Search for the title fragment before re-running, or you file the
  duplicate your dedupe step exists to prevent. Recipe: `references/issues.md` → *`gh issue create`
  takes no `--json`*.

## Verification

- The workflow's own reference file defines done for that task.
- Cross-cutting: every claim about remote state (CI, merge, release,
  issue state) is backed by a fresh `gh` read, never memory.
