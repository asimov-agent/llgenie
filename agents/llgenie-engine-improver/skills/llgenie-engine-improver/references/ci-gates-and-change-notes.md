# CI gates: reading a red run, and the change→note gate

## Read the failing job's own log before any red/green claim
- `gh pr checks <n>` gives name, status, conclusion and the job URL. A `conclusion` is a verdict, not a cause — open the job's log and quote its error line before diagnosing.
- Fetch the log with `gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs`. If it errors parsing escape sequences, add `--allow-escape-sequences`; one failed call is not evidence the log is unretrievable.
- While the run is `in_progress` the log endpoint answers "run is still in progress" / BlobNotFound. Say "error line not yet retrievable — unlocks at run completion" and do not invent a cause.
- `jq` type conflicts on joined check-run fields are common: pull the fields in separate `--jq` calls or via a Python one-liner instead of one deep join.

## The change→note gate (`scope` job / check-docs)
- A behavioural change (a `scripts/*.py` or `containers/` file) owes three committed artifacts or `scope` reds: `agent-wiki/<stem>.md` note, `docs/changes.d/<stem>.md` fragment, and the regenerated `CHANGES.md` index row. Mirror the format of the most recent merged note under the same stem prefix.
- The gate diffs `base...HEAD` — committed history only. Files left untracked in the worktree are invisible to it, so a local `make check-docs` reds until the trio is **committed**. Commit, then re-run the gate; do not chase a phantom defect.
- Render the index with `make changes-index`; verify with `make changes-index-report` — expect `N fragment(s) … N note(s) … 0 defect(s)` and `CHANGES.md: N row(s) committed, N rendered — current`.
- The render is deterministic over ALL fragments. If `origin/main` carries a fragment whose index row is missing (merge drift from an earlier merge), the render folds that older row in next to yours. A two-line `CHANGES.md` diff is then correct, not churn — state it in the PR thread rather than hand-editing the index.

## Local pre-push hygiene for a docs/behaviour PR
- `scripts/lint_linefeeds.py` (run with the suite venv python) requires a trailing newline on every tracked text file and blank-line separation between markdown sections — a note file authored without a final newline reds it.
- Check the new files for CRLF before pushing (terminal `grep -l $'\r' <files>`, or `search_files` for a trailing `\r` pattern) — a Windows-authored fragment reds the same gate.
- Push the fix as a normal commit on the same branch and re-read the fresh CI verdict at the NEW head. A stale green/red from the previous head is not the current truth.
