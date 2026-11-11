# Authoring your own PR in this repo: the body-gate contract

When this lane opens a PR (an audit record, a docs/agent-profile change, a fold vehicle), the `scope`
and `guard` jobs read the PR **body text** and the **commit message** as gate input. Get the headers
wrong and the PR reds on text, not code. Read the failing job's own log for the exact message each
time — do not assume a repeated red is the same cause.

## Header lines the gates parse

| line | what it must carry | pitfall |
|---|---|---|
| `AGENTS:` | a **commit** sha (e.g. the `origin/main` tip at open) | citing the AGENTS.md **blob** id fails `check-pr-agents-line` — it wants a commit object in history, not a blob |
| `BASE:` | the **full** 40-char sha and the literal phrase `(== origin/main at open)` | a short sha, or a paraphrase like `(at branch cut)`, fails; the gate wants the full sha plus that exact parenthetical |
| `SYNC:` | a sync line when the PR touches `agents/` | required by `check-pr-sync-line` on any `agents/` change |
| `OPENSPEC:` | the name of an OpenSpec change dir | required by `check-pr-openspec-change`, which treats `agents/` as **behaviour**, not docs-only |

## `agents/` is behaviour: it needs an OpenSpec change dir

A change to `agents/<profile>/…` is not "docs-only" to `check-pr-openspec-change`. Create the change
dir (`make openspec-new NAME=<slug>`); when it is genuinely docs/paths-only, the validator's own tip
permits `.openspec.yaml` with `skip_specs: true` plus `proposal.md` + `tasks.md`. Validate with the real
target (`make openspec-validate NAME=<slug>` — omitting `NAME=` returns rc 2 and reads like a failure).
The container may create the dir root-owned; `sudo chown` it before writing.

## Claiming a close: `check-pr-acceptance` and `check-pr-closing`

- **`check-pr-acceptance` reds when the body claims `closes #N` but #N's `## Acceptance criteria` boxes
  are unticked.** That is the by-design pre-review hold — the reviewer ticks them at finalize; a tester
  must not tick them. But if the PR does not actually complete the issue (a docs-only slice against a
  fleet-wide umbrella, an audit record that does not close its target), the fix is to **remove the close
  claim entirely** from body and commit subject/body — not to fight the gate.
- **`check-pr-closing` flags any `#N` that appears without an adjacent close** (`closes|fixes|resolves
  #N`) as a claim-without-close. Reference the issue in prose under a "Not covered"/notes section
  without the keyword, or drop it. A subject ending `(#N)` counts as a claim and must match a real close.

## Prove the gates locally before pushing

```
python3 scripts/check_pr_closing.py check --body-file <body.md> --head <branch> --base origin/main --rev HEAD
```

plus the acceptance-form / agents-line / sync-line / openspec gates the CI `guard` job runs. A green
local pass on the committed tree is the pre-push proof; the remaining `check-pr-acceptance` red (unticked
ACs on an issue you DO close) is stated as the by-design hold, never silenced.

## A body-only fix is a re-run, not a push

Editing the PR body does not change the head, so it triggers no new run. After `gh pr edit --body-file`,
re-execute the failed jobs with `gh run rerun <run-id> --failed` (the guard reads the LIVE body) — do
not push an empty amendment to force a run.

## `git reset --soft origin/main` CORRUPTS a branch when main advanced

During a long session `origin/main` moves. `git reset --soft origin/main` then stages **main's newer
commits into your branch**, so the next commit would delete whatever landed on main since you branched
(other lanes' SKILL edits, new scripts/tests). Never reset onto a moved `origin/main`. Rebuild clean:
hard-reset the tracked files back to your own last good commit (`git reset --hard <your-commit>` or
`git checkout -- .`), re-apply your edits, commit once. If you must squash, `git reset --soft
<your-own-previous-commit>`, never onto `origin/main`.

## Authoring conventions

- **`$HOME` portability (owner standing rule).** Any doc, skill, SOUL, reference, or PR body you author
  writes `$HOME`, never `/home/<user>`. Convert executed-shell paths (worktrees, `docker run` mounts,
  redirects, CLI args); leave parsed literals (Python `<<'PY'` heredocs where `$HOME` will not expand,
  sys.path literals) unless the harness parses them.
- **A completion guard that fires "no task-relevant mutation" may be BLIND, not right.** A detector
  that counts repo-worktree `changed_paths` registers a legitimate profile-skill edit, a filed issue,
  and worktree-landed + CI-merged work as zero mutations. Verify the change on the polled tree
  (`git show origin/main:<path> | grep -c '/home/<user>'` → 0, PR merged) and, if it is genuinely
  landed, refuse the guard with the mechanism named — never manufacture a dummy repo edit or a dummy
  test to move the number; that is the exact defect the guard exists to prevent.
