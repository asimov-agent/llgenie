# Issue-bot work in llgenie: triage, close, implement, land

What it costs time to learn when acting as the issue bot on this repo, in the order the work happens.

## 1. Before implementing anything from a CI failure, check what main already fixed

The repo's bots file a work item for nearly every red run, and a fix for the same root cause may have
landed minutes ago. Before you write a line:

```bash
git fetch origin main -q && git log --oneline origin/main -5
```

Read those subjects, and for the suspect function `git log origin/main -S '<symbol>' --oneline`. A
symptom fix that touches the same call site is easy to miss inside a long issue body, and implementing
past it produces a duplicate PR that then conflicts on rebase.

## 2. The run-failure reactor's backlog is mostly history

`scripts/run_failure_reactor.py::superseded()` (a `pull_request` run whose PR is merged/closed, or a
`push` run a later run of the same workflow already turned green) means the reactor files NOTHING for
those today. Issues filed before that guard existed are still open and read like live defects. Verdict
them by re-measuring on the current tip: open the named script, grep for the guard/fix the issue asks
for, and check whether the named workflow has been green since (`gh run list --workflow <file> --limit 6`).
Close with the finding as evidence, not with "stale".

Recurring close reasons that are usually right:

| shape of the issue | verdict |
|---|---|
| `Resource not accessible … addComment/addComment 403` | token/permissions fix already landed; check the workflow's `permissions:` block and recent green runs |
| `No module named pytest` in a `test-published-*` row | the recipe ran pytest on the runner's bare python; the fix moves it into the test image |
| a macos-only job | the queue label has no runner; find the one macos-queue issue and file no second one |
| a fork PR's `denied: … Write organization package` | by design for a fork head (read-only token); not a defect |
| `no checks reported on the '<branch>' branch` | fixed by a guard in the sweeper (`gh pr checks` exits non-zero for a branch whose workflows never ran) |

## 3. Closing/commenting many issues: JSON payloads, never shell heredocs

`gh issue close --comment "…"` breaks on backticks, parentheses and `$` inside a Bash command line
(the parser rejects the whole call). Use a small python helper that posts the body as JSON:

```python
import json, subprocess
body = json.dumps({"body": text})
subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/issues/{n}/comments",
                "--input", "-", "-H", "Accept: application/vnd.github+json"],
               input=body, capture_output=True, text=True)
subprocess.run(["gh", "api", "-X", "PATCH", f"repos/{REPO}/issues/{n}", "--input", "-"],
               input=json.dumps({"state": "closed", "state_reason": "not_planned"}),
               capture_output=True, text=True)
```

Keep the comments and bodies in a JSON file in the scratch dir, one key per issue, and iterate — one
typo then costs one entry, not a re-typed command.

## 4. Remotes are swapped relative to AGENTS.md in this checkout

`origin` is the UPSTREAM (`asimov-agent/llgenie`); the fork is `fork` (`andyholst/llgenie`). So:

```bash
git push -u fork <branch>
gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<branch>
```

AGENTS.md's examples assume `origin` is the fork — read `git remote -v` once, do not trust the doc's
name.

## 5. `make openspec-new` leaves a root-owned change directory

The CLI runs in the container `-u root`, so `openspec/changes/<name>/` arrives root-owned and
`write_file` fails with `Permission denied` on the first `proposal.md`. After `make openspec-new`:

```bash
sudo chown -R "$USER": "openspec/changes/<name>"
```

## 5b. A CONFLICTING PR gets no CI runs at all

A PR whose head conflicts with `main` produces **no workflow run**: `gh pr checks <n>` says "no checks
reported", `gh run list --branch <branch>` is empty, and an empty commit or close/reopen does not help.
Rebase onto `origin/main`, push, and the run appears. Right after a force-push GitHub's lazy mergeability
can still report `CONFLICTING`/`DIRTY` for a minute — re-read `gh pr view --json mergeable,mergeStateStatus`
before believing it.

## 6. Drive a bot make target end to end with a fake `gh`

No network needed, and it proves the exit-code contract the workflow depends on:

```bash
d=$(mktemp -d)
printf '#!/usr/bin/env bash\ncase "$1" in api) echo ""; exit 0;; pr) echo ""; exit 0;; *) exit 1;; esac\n' > "$d/gh"
chmod +x "$d/gh"
out=$(mktemp)
PATH="$d:$PATH" GITHUB_OUTPUT="$out" make <target> REPO=… RUN_ID=… ; echo "rc=$?"; cat "$out"
```

Do this for both callers when one resolver serves two bots with opposite answers (a merge gate that must
fail loudly vs a repair bot that must no-op).

## 7. The `agent-wiki/` entry's PR line

Write the entry in the change commit, then replace the `PR: _this branch_` placeholder with the real
number once the PR exists — one small follow-up commit. `make check-docs` accepts an entry with an issue
reference alone, so the placeholder passes CI and is easy to leave behind.
