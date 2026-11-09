# Bot PR hygiene-gate battery (run locally before the first push)

Every gate below is cheap and local. Run each `make <target>` against the branch's diff versus the **live base tip you fetched this session** (not a stale fork `origin/main`), then fix the failure before pushing — a push that reds a hygiene gate costs a review cycle and un-arms auto-merge.

| Gate | What it demands | Silent trap |
|---|---|---|
| `check-pr-closing` | an **adjacent** `closes #N` in the commit message | a subject suffix `(#N)` and an `Issue: #N` body line are not closes — the gate wants `closes #N` |
| `check-pr-base` | HEAD contains the base tip | stale base reads as a huge diff and skews every other gate; `git merge-base --is-ancestor <base-tip> HEAD` |
| `check-pr-openspec-change` | `OPENSPEC: <name>` at **line start** naming an active `openspec/changes/<name>/` | inline on the SYNC line fails — the regex is anchored `^OPENSPEC:` |
| `check-pr-agents-line` | an `AGENTS:` line **plus** a `BASE:` line citing the base sha with `AGENTS.md` byte/line stats | applies whenever the committer email is in BOT_EMAILS; the `AGENTS:` line's own format is anchored — a bare sha (`AGENTS: <sha>`) reds `no AGENTS: <sha> <bytes>b <lines>l line`, it wants the counts glued to their unit with no space: `AGENTS: <sha> 91766b 1363l` |
| `check-pr-sync-line` | a `SYNC:` line for every changed agent profile | — |
| `check-docs` | any `scripts/*` change owes a note + fragment + index row | see below |

## check-docs: the change-note trio

A behavioural change under `scripts/*` (tests are exempt) owes three artefacts, stem-matched:

1. `agent-wiki/<stem>.md` — the note.
2. `docs/changes.d/<stem>.md` — the fragment row.
3. `CHANGES.md` — regenerate with `make changes-index` (never hand-edit).

The stem must match between note and fragment; the index gate refuses a note with no fragment and a fragment with no note. Run `make check-docs` locally to confirm before pushing.

## check-pr-acceptance is a designed hold, not a defect

The gate reds when a PR **closes** an issue whose `## Acceptance criteria` are unchecked. This is the deliberate chicken-and-egg contract (#1644): a PR must not tick its own criteria — the **reviewer verdict writes each criterion back**. So `check-pr-acceptance` red saying "acceptance item N is still `- [ ]`" is the expected state until the reviewer lane ticks it. Do not self-tick to go green.

- A criterion the change genuinely **does not** satisfy (measured non-reproducible, out of scope): declare it in the PR body under `## Not covered`, as a bullet whose **leading three words match the criterion text, normalized** (strip punctuation/case), plus a linked work item. A near-miss bullet does not match and the gate keeps the violation.
- A criterion the change **does** satisfy (e.g. "a genuine red still reds" when you added no weakening): leave it for the reviewer's write-back. Declaring it out-of-scope is dishonest and blocks the honest merge.

## The verdict workflow checks out `main`, not your PR branch

`ci-verdict` runs on `workflow_run` with `actions/checkout ref: main` — it executes **the default branch's** `ci_verdict.py`. While your PR is open, a `ci-verdict`/`scope` red at your head is the **pre-existing** gate redding a CI run whose guard failed (e.g. the acceptance hold), **not** your change in action. Never diagnose your own change from a verdict run's log before it merges; verify locally (guard-prove) instead.

## The battery is spread across separate SCRIPTS — pass each gate to the right one

There is no single `check_pr_hygiene.py <gate>` entry point: `check_pr_hygiene.py` only accepts `check | report | agents-line | sync-line | openspec-change | changes-index` (anything else errors `invalid choice`, e.g. `closing`). `check-pr-closing` and `check-pr-authors` are their own scripts (`check_pr_closing.py`, `check_pr_authors.py`). To prove a gate against the LIVE body without a push:

```sh
# body is what the agents-line gate reads, not the commit:
gh pr view $N --repo <o>/<r> --json body --jq .body > /tmp/live-body.md
gh api repos/<o>/<r>/pulls/$N --jq '.base.sha'   # == the sha CI's origin/main resolves to
python3 scripts/check_pr_hygiene.py agents-line   --head <head-sha> --base upstream/main --body-file /tmp/live-body.md
python3 scripts/check_pr_hygiene.py sync-line     --head <head-sha> --base upstream/main --body-file /tmp/live-body.md
python3 scripts/check_pr_hygiene.py openspec-change --head <head-sha> --base upstream/main --body-file /tmp/live-body.md
```

## A PR-body slab defect is fixed by EDITING THE BODY, not amending the commit

`check-pr-agents-line` reads `PR_BODY`. Append the slab to the existing body and `gh pr edit $N --body-file <file>` — then a `--failed` guard **rerun re-reads the live body**, so no commit/amend/force-push is needed. Put the slab at the end under a `---` rule: the `AGENTS:`, `BASE: <sha> (== origin/main at open)`, and (when the diff touches `.github/workflows/` or other non-docs surface) `OPENSPEC: <name>` lines, each at line start. A diff touching `.github/workflows/` is NOT docs-only — it owes the `OPENSPEC:` citation even when the change is a workflow/test tweak.

**Never report a PR "complete" or "merge-ready" from local gate passes alone.** The slab defect above was self-introduced and invisible locally because the local file gates never read the PR body — only the live guard does. Before claiming green, re-read the guard's per-step `conclusion` (`gh api repos/<o>/<r>/actions/runs/<run>/jobs`), not the check badge, and confirm the only non-success step is a gate you cannot clear yourself (the `check-pr-acceptance` designed hold), never a hygiene step you own.

## Computing the `AGENTS:` counts, and reading trailers back

Derive the two numbers from the **staged** diff — never reuse one for both, and never count the working tree after `git reset`:

```sh
git add -A
git diff --cached --numstat | awk '{a+=$1; d+=$2} END{print a" added lines, "a+d" changed lines"}'
git diff --cached --numstat | awk '{bytes+=$1} END{print bytes}'   # line-based proxy; cite it as such
```

If you also put `AGENTS:`/`BASE:` in the commit message, read the parse back rather than trusting the write: `git log -1 --format='%(trailers)'` prints **only** the final trailer block. A `BASE:` line separated from the last trailer by prose, or placed above the `AGENTS:` line with a blank in between, is silently not a trailer — verify it appears in `%(trailers)` or accept that only the PR body carries it (the agents-line gate reads the PR body, not the commit).

## Guard-prove before trusting a new test

Run the new test against the **old** source first: it must fail (name the violation). Only then run it against the fixed tree and see it pass. A test that has only ever run green proves nothing.
