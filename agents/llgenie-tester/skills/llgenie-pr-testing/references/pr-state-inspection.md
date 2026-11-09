# Inspecting PR and head state without flooding the context

The llgenie tree carries ~3,000 files. Answer "does this exist at the head" with targeted
object reads, never with a whole-tree listing piped into grep — each such grep dumps tens of
KB into the transcript and a handful exhausts the context before the verdict is written.

## Existence, content, size at a ref

```bash
WT=/path/to/worktree          # or any repo dir; the sha matters, not the worktree
REF=origin/pr-<n>             # or a sha

git -C "$WT" cat-file -e "$REF:path/to/file"; echo "rc=$?"   # rc 0 = present
git -C "$WT" cat-file -s "$REF:path/to/file"                  # size in bytes
git -C "$WT" cat-file -p "$REF:path/to/file" | head -20       # content
git -C "$WT" rev-parse "$REF:path/to/file"                    # git blob id (short it for the report)
```

Directory listing — only for one directory, never recursive over the repo:

```bash
git -C "$WT" ls-tree --name-only "$REF:docs/changes.d"
```

`git ls-tree <ref> <dir>` (two bare args) **silently returns the commit object**, not the
directory listing — the colon form is the only one that lists a subtree.

## Grep the whole tree for a literal, not just the workflows dir

A criterion that names an env var or config value is not necessarily satisfied in
`.github/workflows/`. Engine parameters live in `containers/engines/params/*.json`; image-level
tunables live in the Dockerfiles. A workflow-only grep reports a false "missing":

```bash
grep -rn 'UV_HTTP_TIMEOUT' "$WT" --exclude-dir=.git | head
```

## Confirm which sha you are measuring

A worktree can sit at a different commit than the PR head. Read through the ref explicitly
(`git fetch origin +refs/pull/<n>/head:refs/remotes/origin/pr-<n>`), then use `$REF:path`.
Before any "flake vs real" or "landed vs not" claim, print `git rev-parse --short HEAD` and the
ref sha side by side; a measurement without the sha is a claim about time.

## Re-verification after a rebase

1. `git merge-base --is-ancestor <base-sha> <head>` must exit 0. Exit 1 means the head still
   carries the pre-rebase base — report blocked rather than verifying a stale premise.
2. Re-derive every criterion at the new head; never carry a previous head's "verified" forward.
3. Each verdict row records the base sha **and** the head sha it was measured at.
4. **A ticked acceptance box records the sha it was measured at** — the tick provenance reads
   `proven: reviewer=<bot> comment=<id> head=<sha> run=<id>`. When the PR head has advanced past
   that sha, the tick is evidence about the *old* head only. Re-measure every criterion at the
   live head before endorsing it; a prior-sha tick plus a fresh green CI run is not the same as
   criterion-level proof at the current head.
5. **A green CI run at the current head certifies the suite, not the criterion mapping.** Read
   the changed lines and run the targeted test module at the head to map each criterion to
   evidence (the pass count and the node id of any regression test). Quote the run id for the
   suite and the per-module pass count for the criteria — they are two rows, not one.
6. **A `rebase --continue` commit fails `make check-pr-closing` — rewrite its message.** Resolving a
   conflict during rebase writes a generic subject (`... resolve conflict ...`), which carries neither
   an adjacent close nor the `(#N)` suffix the scope gate looks for. Amend before pushing: subject ends
   `(#N)` (`type(scope): summary (#N)`) AND the body carries `Issue: closes #N`. `rebase --continue`
   produces one commit with this generic text, so `git commit --amend` (not an interactive squash) is
   the fix; run `make check-pr-closing` locally before the force-push so the revisit is free.
7. **A conflict in a GENERATED file is regenerated, never hand-resolved.** `CHANGES.md` is rendered
   from the `docs/changes.d/*.md` fragments, so a rebase conflict there is "both sides added a row":
   resolve by taking either side and re-running `make changes-index` (it rewrites the whole index from
   the fragments on disk, so both rows survive). Separately: a rebase conflict against a live `main`
   usually means main moved while you worked — after resolving, `git diff origin/main --name-status`
   must show **exactly** your own files; anything else means the resolution imported foreign content.

## A red `[check-pr-base]` mid-dispatch is usually MAIN ADVANCING, not a foreign-commit leak

While you test, a sibling PR merges and `origin/main` moves past your branch's base. The rerun's
`linux / unit` then fails `[check-pr-base]` and the gate prints the PR's OWN commits as "foreign" —
because CI checks out the PR merge-ref (`refs/pull/<n>/merge`), not the tip, so the branch's own
carries read as reachable from the (different) branch ref. It looks like an #845 leak and is not.

Diagnose before anyone "fixes" it:

```bash
git fetch origin main
git merge-base --is-ancestor origin/main <head>; echo "rc=$?"   # rc 1 = stale
git merge-base <head> origin/main                              # the OLD base == the stale tell
# run the gate against the TIP, not the merge-ref:
check_pr_base ... --base origin/main --rev <tip>               # prints STALE-but-clean, rc 0
```

`STALE-but-clean` (every carried commit is its own) is the verdict; a true foreign-commit red names
commits reachable from *another* ref. The remedy is a REBASE onto the new `origin/main`, no code
change — hand it to the merge-conflict lane. Re-measure every other board PR against the new main
sha: a board snapshot taken before the sibling merge names the wrong baseline, and a stale `main`
sha quoted in a report draws a correction.

## Choosing which PR to test when handed a board

A dispatch that names several open PRs is asking which one a tester can actually advance. Rank by **unproven criteria**, not by recency:

1. One call per PR gets the shape: `--json number,state,isDraft,headRefOid,baseRefName,mergeStateStatus,headRepositoryOwner`. Check `headRepositoryOwner.login` before assuming a fork head — a same-repo head (`asimov-agent`) opens against `main` just the same, and only the fork head needs `--head <fork-owner>:<branch>`.
2. Map each PR to the issue it closes, then count that issue's boxes: `grep -c '^\s*- \[x\]'` and `grep -c '^\s*- \[ \]'` on the body. **Take the PR with an unticked criterion.** A PR whose criteria are all ticked and reviewer-verified hands the tester nothing to derive — re-deriving a reviewer's tick is a duplicate row, and saying so is the honest report.
3. Read the unticked criterion's own words before claiming it. "Contains no failing gate" / "is green in CI" is tester work; "is green on the same job that failed" may be circular (a red-job-triage §11) — that is a find-and-report job, not a failure to announce.
4. `gh pr checks` prints `skipping` rows for path-filtered jobs. `skipping` is neither a pass nor a fail and never blocks a verdict; do not let it read as a red or as coverage.
5. Docs-only and already-verified PRs go last: the tester lane's row on them is a pointer to the owning lane, not evidence.

## An issue's acceptance text can diverge from what its PR shipped — name it

`make check-pr-acceptance` holds the issue's `## Acceptance criteria` LITERALLY: an unproven
`- [ ]` item stays a violation even when the merged PR provably achieves the item's intent with
different output. Read the shipped code before writing criterion evidence — the criterion may
describe the ORIGINAL design while the fix took another route.

The concrete case: #2138's criterion 1 said the verdict prints `behind_by=<n>`, and criterion 4
said the report prints which mode (`PR_NUMBER` commit count vs empty-range fallback) judged the
branch. PR #2183 shipped a DIFFERENT mechanism — `--head-ref-name`/`--pr-number` classify the
head's OWN refs and emit `STALE … own commits carried (N)` with no `behind_by=` and no mode line.
The criterion's behaviour (a merely-behind branch passes after main advances) WAS proven — `python3
scripts/check_pr_base.py check … exit 0` — but the literal text it demanded was absent.

For each unproven criterion: run the literal command at the head, capture exit code + real
output, and state the divergence explicitly — "behaviour proven (branch passes, exit 0) but text
diverges: criterion says X, code emits Y" — plus the reconciliation path (rename the criterion
to the shipped text, or make the code emit the literal output). Do NOT mark a criterion proven
when its literal text is absent; the reviever/writer needs the divergence named to tick honestly.

## Three evidence states, never blurred

| state | what exists | what you report |
|---|---|---|
| failed | job ran, concluded failure | test name, job id, sha, failing step |
| not yet run | no run of that workflow at the head | pending; name the run that *does* exist and its older head; state the dispatch needed |
| green | completed run at the head | the only state that supports a pass |

Never substitute an older-head run as the head's evidence, and never read a run-level
`cancelled` as "the job failed" — judge the job.

Arm a watcher for the missing run (a background loop that exits when the run appears) instead of
polling in a turn loop, and hand the partial verdict — verified criteria plus the one named
pending — to the planner.

**Post the durable bookend on the PR/issue before relaying.** The comment on the PR (or issue) is
the record a stranger can find; the planner message is a relay of the same lines. If the relay is
declined (a progress guard on a read-only test lane, where no implementation mutation is
available or appropriate), do not retry the same call in a loop — the bookend already carries the
evidence. One retry with a materially different shape is the most a blocked relay earns; after
that, the PR comment stands as the verdict's home.

## execute_code / shell-building traps that cost whole calls

- **Do not interpolate shell text containing braces into an f-string.** YAML `${{ ... }}`, regex
  character classes like `[,}]`, and any `{`/`}` make Python parse the braces and raise
  `SyntaxError: single '}' is not allowed` or `f-string: invalid syntax`. Build the command as a
  plain string literal, or concatenate a variable: `cmd = "grep -n " + pat + " " + path`.
- **Backslashes inside f-strings**: `"\x1b"`, `"\|"` and similar raise SyntaxWarning/error.
  Use raw strings (`r"..."`) or avoid the escape entirely (strip ANSI in a separate `sed`).
- **A helper that already passes `shell=True` cannot take another `shell=` keyword** — that is
  `TypeError: run() got an unexpected keyword argument 'shell'`. Call `subprocess.run(cmd,
  shell=True, capture_output=True, text=True)` directly.
- **Slice before printing** (`out[:1500]`). When a tool result says "too large, saved to a file",
  do not re-issue the same query — narrow it (one path, one grep, `--jq` projection) instead.
