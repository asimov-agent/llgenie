# Traps that cost real time (repo-specific)

Load this when a command's output reads as a failure, a red looks like it might be the PR's, or a
post may not have landed. Each entry is a mechanism plus the discriminating command.

- **`docs/ARCHITECTURE.md` is generated and its census goes stale fast, and it goes stale
  *again* the moment anything merges.** The `architecture-bot` (cron `47 */6 * * *`, issue
  #449) rewrites it as one issue + one PR, and the numbers describe the commit the bot
  measured. A bot PR rebased onto newer `main` keeps the OLD numbers and lands already
  wrong — and a refresh measured against a base that merges before its own merge is wrong
  too. Always census the branch's **current** merge base (`git rev-parse origin/main`), not
  the base you measured an hour ago. Verify with the bot's own census
  (`scripts/architecture_bot.py:tracked_files` is just `git ls-files`):
  ```bash
  git ls-tree -r --name-only <head^> | wc -l
  git ls-tree -r --name-only <head^> -- scripts | wc -l
  git ls-tree -r --name-only <head^> -- tests | grep -c 'test_.*\.py$'
  ```
  A mismatch on `HEAD^` is a blocker (stale census ⇒ `do-not-merge`), and `git ls-tree`
  counts differ from `ls -d dir/*/` — use the `git` form, that is what the generator counts.
  Reviewing a census PR means recomputing **every** number it touches, not the headline one: the
  qualifiers in the same sentence (`skills/engines/` subdirectory count plus its `README.md`,
  `openspec/changes/` directory count, the `N tests/test_*.py` figures — which appear in two places)
  are claims too, and each is one `git ls-tree` away. Finish with `make check-docs` (exit 0, and quote
  its `[check-docs] ok: …` line) because that is the gate the change must pass. Run it directly as
  `python3 scripts/check_docs.py check` — it takes only `--root`/`--base`, **not** `--rev` (`unrecognized
  arguments: --rev` is a CLI-shape error, not a docs failure), and with no `--base` it lints the whole
  tree at the checked-out head; its `ok:` line counts every user-facing make target, every
  `agent-wiki/` entry's index row, and the `CHANGES.md` link set. Say plainly which
  number you could **not** re-derive from the tree (e.g. an engine-count line that reads the registry)
  instead of letting silence imply verification.
  Fixing a census is legitimate review remediation: edit only the numbers, keep every
  non-census sentence, commit as `Asimov Agent <support@docondee.com>` (or `Andy Holst
  <andy.holst@protonmail.com>`) so `check-pr-authors` passes, push on top (no force-push),
  and re-run `make lint check-docs`.
- **`tests/conftest.py` needs the gguf venv, so run a single test module with `--noconftest`.** It
  imports `scripts.llgenie_serve` (gguf+numpy) and a plain venv dies with exit 2 and no output — the
  silent exit 2 is a missing import in the venv, not a failing test. Two things make a scratch venv
  work in a repo worktree: `--noconftest` and `python -m pip install -q pygments` (pytest imports it,
  and without it the failure looks identical to the conftest problem). Then:
  `python -m pytest --noconftest -q -p no:cacheprovider tests/test_<name>.py`; for the whole suite use
  the container path (`make test-unit`, ~12–13 min). Do not conclude "the tests do not run here" from
  one empty log — retry with the module installed and quote the real `N failed, M passed` line.
  **A module that imports a sibling under `scripts/` (e.g. `from scripts import check_pr_closing` which
  then imports `base_ref`) needs `scripts/` AND the repo root on `PYTHONPATH`, or it dies at collection
  with the same exit-2 / bare `ImportError` and reads like the empty-log conftest artifact — a clean
  env is not a broken test.** Prefix the exact same command with it and the collection error becomes a
  real green: `PYTHONPATH="$PWD/scripts:$PWD" python -m pytest --noconftest -q -p no:cacheprovider
  tests/test_<name>.py`. Measure the module at the PR head in a worktree and quote the full count
  (`27 passed`) — that count is the acceptance evidence the earlier bare-venv run failed to produce, so
  a "could not collect" in your own prior note is a reason to re-run with the path set, never a
  finding.
- **Prove where a red comes from before you attribute it to the PR: reproduce it on `origin/main`.**
  A board can show five red PRs that share one broken default branch, and holding each of them parks
  work for a defect it does not carry. Check `main`'s last run first, then reproduce:
  ```bash
  git -C "$HOME/repository/git/llgenie" worktree add --force --detach ../llgenie-wt/vmain origin/main
  cd ../llgenie-wt/vmain && python -m pytest --noconftest -q <the modules named in the failing job>
  ```
  Same FAILED set ⇒ the red is **not in the diff**: write "not green, for a reason outside the diff",
  name the two commits that introduced it, and place **no hold** (a hold on such a branch parks it for
  someone else's defect). The unblock is the `main` fix, not a change on the PR. Quote the local
  counts (`4 failed, 66 passed` at the PR head vs `6 failed, 187 passed` on `main`) so the attribution
  is a measurement rather than an opinion. Never fold a shared red into a per-PR verdict without it.
  When the `main` fix itself comes up for review, close the loop the same way: run the **same modules**
  at the fix's head and quote both counts (`6 failed, 187 passed` before → `0 failed, 193 passed`
  after) instead of reading a green job, because a local pass proves the change and only
  `linux / unit` proves the gate.
- **Several PRs failing the *identical* assertions is a shared base, not several authors making the
  same mistake — and `main` passing does NOT mean the diff caused it.** A branch cut before a commit
  that added both an artifact and its index/metadata row fails "missing row" assertions while `main`,
  which has both, passes: the diff looks guilty and is innocent, and the remedy is a rebase, not an
  edit (adding the row in the diff duplicates it on rebase and reds something else). The cheap
  discriminator is a two-sided count, before any verdict — run it, never eyeball it:
  ```bash
  python3 scripts/pr_watch.py --changes-index origin/main <pr-head-sha> [<more heads…>]
  # origin/main   wiki=223 notes=223 preflight=yes base=7db4ac99 verdict=indexed
  # a9fe2fc9      wiki=222 notes=221 preflight=no  base=5a367d42 verdict=SHORT by 1 note(s)
  # 2bf9483f      wiki=210 notes=0   preflight=no  base=0ddfda8b verdict=MISSING-DIR (…rebase, do not hand-add)
  ```
  It prints `indexed` / `SHORT by N` / `MISSING-DIR` / `EXTRA` plus the merge-base per ref, so one call
  classifies a whole sweep: `MISSING-DIR` means the branch predates `docs/changes.d` entirely (rebase),
  `SHORT by 1` is the single missing-note shape, and equal counts on a branch but red on `main` means the
  red is real. Its fixture form is `pytest -q scripts/test_pr_watch.py`. Fall back to the raw loop only
  when the script is unavailable:
  ```bash
  for r in origin/main refs/remotes/origin/pr<n>; do
    printf '%s notes=%s rows=%s\n' $r \
      "$(git ls-tree -r $r --name-only | grep -c '^agent-wiki/.*\.md$')" \
      "$(git ls-tree -r $r --name-only | grep -c '^docs/changes.d/.*\.md$')"
  done
  git cat-file -e refs/remotes/origin/pr<n>:docs/changes.d/<expected>.md && echo present || echo absent
  ```
  Equal counts on `main` + one short on the branch + the file absent on the branch ⇒ **stale base**: say
  "rebase, don't edit" and place no hold (a rebase needs no issue). Getting this wrong is a retraction-
  worthy error in the direction that accuses an innocent PR, so run the count *before* writing the
  verdict — and when you have already written it, retract on the PR with the two numbers, saying which
  of your own inferences was wrong, rather than quietly appending a correction.
- **Measure a per-PR delta against the PR's OWN base (or the API's `files` patch), never against a
  moved `live/main` tip — a stale base shows the inverse of everything that landed after the branch
  point, and reads as the PR carrying foreign files.** Diffing `live/main-tip..head` on a branch cut
  before several merges reports every file those merges added as *removals* in "your" diff (measured
  10 files / 294 deletions where the true PR was 4 files / 49 insertions). The authoritative per-PR
  content is GitHub's own patch:
  ```bash
  gh api "repos/<o>/<r>/pulls/<n>/files" --paginate --jq '.[]|select(.filename=="CHANGES.md")|.patch'
  git diff "$(git merge-base <live-main> <head>)" <head> --stat   # per-PR, not tip..head
  ```
  A **foreign-looking row** in that patch (a `docs/changes.d`/`CHANGES.md` row for a different issue
  that belongs to an already-merged PR) is usually **base-carry, not a duplicate**: the branch snapshot
  predates the row landing on main, so the row rides in byte-identically and the merge is a no-op there.
  Discriminate with the row's bytes, not a read — identical md5 on head and on live main ⇒ carry
  (no-op merge, note-only, **no red, no hold**); different md5 ⇒ a real duplicate the PR introduces.
  ```bash
  git show <head>:CHANGES.md | grep '<slug>' | md5sum
  git show <live-main>:CHANGES.md | grep '<slug>' | md5sum   # equal ⇒ base-carry
  ```
  When a *local* ref disagrees with the API (`git merge-base --is-ancestor` says a sha is an ancestor
  yet `git show <that-sha>:<file>` lacks content the API shows both places), the local object is stale —
  trust the API's tree over the local object and say so; do not build a finding on the stale copy.
- **A fix that greens previously-red tests must CORRECT the assertion, not delete it — read the test
  diff before you say "fixed".** Deleting or loosening the failing assertions turns the board green
  and the change wrong: those assertions are usually the correct alarm for an incomplete code change
  (a group of jobs removed from CI, but three of six test files reconciled). The correction shape is
  an assertion that still fails if the defect comes back — `assert callers["macos"] == (...)` becoming
  `assert "macos" not in callers` is fine; a deleted block, an added `xfail`/`skip`, or a widened
  `except` is a waiver. The same test applies to a repo rule the diff broke (an inline `python3` in a
  workflow `run:` step): satisfying it means moving the work into `scripts/` or a make target and
  calling that, never editing the rule's own test to permit it. In the verdict say which it was —
  "the six went green because each assertion was updated to the new contract and still reds if the old
  shape returns" — because "tests pass" is exactly what a deleted test also reports.
- **A dedup/normalization change that EMPTIES an invariant reds tests while `main` stays green — that is
  the diff's red, not a shared base.** Removing the last member of a class (the last duplicate canonical
  rule, the last of a roster, the last shard) trips assertions of the form `assert names` ("report must
  name at least one …") that were written when the class was non-empty. The docstring may even say the
  removal is the owner's call — that does not update the test. Discriminate exactly: read the job log for
  the `AssertionError` line, then run the same module at `main` (green there ⇒ own-diff, because a green
  `main` is what proves the red came from the branch). The remedy goes in the SAME change set — assert the
  clean invariant, or inject a synthetic fixture so "name it when present" survives without real-tree
  dependence — never dismiss it as shared base just because `main` is green.
- **Check that a fix issue's acceptance command is the command CI actually runs.** An issue scoped to
  one module (`pytest tests/test_x.py -q`) can be satisfied while `make ci-unit` stays red — so every
  PR remains unmergeable and the lane has spent a push for nothing. Add the widening as a comment on
  the issue (all failing modules, then `make ci-unit` exit 0, then a completed `linux / unit` run quoted
  with its id) rather than silently reviewing against a criterion that cannot close the gate.
- **`gh api …/actions/jobs/<id>/logs` reads EMPTY through `--jq .` and errors on escape sequences
  without the flag — redirect it raw, never pipe it.** The log body is not JSON, so `--jq` returns 0
  bytes and the empty file reads like "no log"; without `--allow-escape-sequences` the call fails
  `the response contains terminal escape sequences`. The working read is
  `gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences > /tmp/job.log`, then grep the
  file. Enumerate the failing step first
  (`gh api …/jobs/<id> --jq '.steps[]|select(.conclusion=="failure")|.name'`) so you read the right
  step, and grep the saved log for `AssertionError|FAILED` lines rather than paging 60 KB.
- **Removing a worktree the terminal is cwd'd into breaks every later call — the persisted shell cwd
  points at a deleted dir, so commands fail with a misleading
  `cd: … No such file or directory` (reported as exit 126 / "not executable").** `git worktree remove`
  does not move the shell out of the tree. `cd` back to the main clone, or pass
  `workdir=$HOME/repository/git/llgenie` explicitly on the removing call and on every call
  after it.
  The dead cwd outlives the worktree that created it: ANY directory removed earlier in the session
  (a scratch worktree from a previous PR, an expired temp dir) poisons every later call, so the same
  `No such file or directory` returns for commands that have nothing to do with that PR.
  **Diagnose it as a cwd problem when the failure repeats identically while file-level tools
  (read/write/patch) still work** — run `pwd`, then pass an explicit `workdir=` on every call
  (or `cd` to a live dir first). **While the cwd is dead, do not keep issuing side-effecting
  commands:** a batch that "fails" this way can still be replayed, and a replayed write-back or
  comment post lands the same mutation twice (duplicate pins, duplicate verdicts). Stop, read the
  wire (`gh api`) to see what actually landed, then re-run once from a live `workdir`.
- **Build a comment body in a file, and read the published body back — not the post's exit code.** A
  `gh api … --jq "…\"$var\"…"` nested inside a double-quoted shell string collapses silently: the
  comment publishes with an empty field where the evidence should be, and `gh pr comment` still exits 0.
  Write the body with a heredoc into a file, post it with `--body-file`, then read back what landed
  (`gh pr view <n> --json comments --jq '.comments[-1].body'`); run any `--jq` that embeds shell
  variables as its own command and let Python do the formatting. **Quote the heredoc delimiter**
  (`<<'EOF'`, not `<<EOF`): an unquoted body expands every backticked span and `$var` as command
  substitution, so the published comment silently loses `fail=0` and `` `pipeline.yml` `` where the
  evidence should be. When one slips out, `PATCH /repos/<o>/<r>/issues/comments/<id>` with the corrected
  body and re-read it — note that `gh api … --jq .body` emits **raw text**, not JSON, so a `json.loads`
  round-trip fails; treat it as a string. A comment that renders a blank number
  is worse than no comment: it reads later as "nothing to report". When one does slip out, post a
  correction at the same sha naming the error and the real value rather than leaving the blank field
  standing.
  **Post the comment as its OWN tool call and confirm its id landed — a post batched with read-only calls
  can be vetoed and never execute.** A per-turn guard that demands a task-relevant mutation can drop a
  whole batch that mixes reads with the post, and no error surfaces on the post itself; the next
  `gh api …/issues/<n>/comments --jq '[.[-3:][]|.id]'` still ends at the previous comment. Issue
  `gh pr comment <n> --body-file <f>` alone, then read the id list back and confirm the new id is present
  before reporting the verdict as posted — a status line claiming "posted" without the id in that list
  is a claim about intent, not a mutation.
- **`gh run list --commit <sha>` lags a fresh push; the API does not.** Minutes after a push it can
  report no runs for a sha that already has three, which reads as "CI never triggered" and invites a
  bogus empty commit. Ask the API instead:
  `gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>&per_page=10" --jq '.total_count, [.workflow_runs[]|"\(.id) \(.name) \(.status)/\(.conclusion)"]'`.
- **`gh issue view --json` has no `timelineItems` (nor `merged`) — enumerating a wrong field prints the whole available-fields list, which reads like a broken command.** For a close-event timestamp use `--json closedAt,closedByPullRequestsReferences`; for `## Acceptance criteria` state read `.body` and grep the checkboxes. **`gh api … --jq .body` emits raw text, not JSON**, so it never round-trips through `json.loads` — treat every such read as a string.
- **`gh pr view --json` field names are not `merged` — there is no `merged` boolean; ask for `state`, and `mergedAt`/`mergedBy`/`mergeCommit` are the merge facts.** `gh pr view <n> --json merged` errors `Unknown JSON field: "merged"` and prints the whole available-fields list, which reads like a broken command rather than a wrong field. A merged PR answers `state=MERGED` plus non-null `mergedAt`; read those two together (`--json state,mergedAt,mergedBy,mergeCommit`) instead of a boolean that does not exist.
- **`gh api` speaks REST field names; `gh run list --json` speaks CLI field names — mixing them returns `null`, not an error.** A REST run object carries `id` and `head_sha`; the CLI's `--json` shape carries `databaseId` and `headSha`. So `gh api repos/<o>/<r>/actions/runs/<id> --jq '{databaseId,conclusion}'` prints `{"databaseId":null,…}` while the run is perfectly live — the null reads as "no such run" and invites a bogus re-dispatch. Read the run you queried with `id`/`head_sha`; use `databaseId`/`headSha` only on `gh run list --json` output. Likewise `commits/<sha>/check-runs` returns an OBJECT holding a `check_runs` array, so iterate `.check_runs[]`, never `.[]` (which errors `cannot iterate over: number` and hides the real job states).

  One API call, both facts, for a fresh head:
  ```bash
  gh api "repos/<o>/<r>/actions/runs?branch=<ref>&per_page=10" \
    --jq '.workflow_runs[] | select(.head_sha=="<sha>") | "\(.id) \(.status)/\(.conclusion) | \(.name)"'
  ```
  A superseded head shows its old runs as `completed/cancelled` after a force-push — those are `no verdict` at the OLD sha, so filter on the NEW `head_sha` before saying anything about the branch.

- **A fork PR head is not a commit in the base repo's object DB — `commits/<sha>/check-runs` answers `422 No commit found for SHA` and `actions/runs?head_sha=<sha>` answers `total_count: 0`, and both read as "no runs" when the PR is fully covered.** This repo's PRs push from `fork` (`andyholst/llgenie`), so the head sha lives on the fork and a base-repo commits/runs lookup cannot resolve it; the 422/zero is a resolver gap, never a verdict. The one call that resolves check-runs for a PR head regardless of where the object lives is `gh pr checks <n> --repo <base>` — make it the primary read, and reach for the raw `commits/<sha>`/`actions/runs` APIs only with a sha you know is on the base (`origin`/`main`). When you need the object itself for `git show`/`git cat-file`, fetch it explicitly: `git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>` (the explicit refspec works where a bare fork-sha fetch errors `upload-pack: not our ref`). Judge only the rows `gh pr checks` returns for the head `gh pr view` names: a prior head's `CANCELLED` unit leg describes the old sha, not the live one. And a peer's earlier "all checks green, CLEAN" is a snapshot — re-read `gh pr checks` at the live `headRefOid` before agreeing: a still-`pending` leg is no verdict and `mergeStateStatus` reads `UNSTABLE`, not `CLEAN`.

- **A newly added text/markdown file must end with a trailing newline, or `lint_linefeeds` reds the docs gate.** A byte-copy taken from a live profile file can lack one, and the scope job fails with `lint_linefeeds` naming YOUR new file — so the red is the diff's, not the shared base's. Check a file's last byte with `tail -c1 <file> | od -An -c` (`xxd` is not always installed; `od` is); a last byte that is not `\n` (a `.`, `|`, any glyph) is the violation. Fix is appending the newline to the display copy, not editing the lint. Run the local `make lint`/`check-docs` over the exact branch before pushing any docs+skills change so this never reaches CI.

  **A peer's "my local lint comes back clean on the same tree" does not contradict a CI red — the local tree is usually at the base, where the diff's new files do not exist.** The gate runs against the branch head/merge ref (patch applied), sees the new `agent-wiki/*.md` and `docs/changes.d/*.md`, and reds on them; the local `lint_linefeeds.py` over an un-patched working tree never loads them. To answer "name the exact file", read the job log, not the tree: the `scope` job prints `LINT FAIL — files missing a trailing newline:` then a bulleted list of paths, which IS the answer. Get the log via the **correct job id** — `gh run view <run> --log-failed` picks the first failing job in the run and can return `log not found: <a different job id>` when `scope` carries the finding but another job (`ci-verdict`) failed first; enumerate with `gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|{id,name,conclusion}'`, take the `scope` job's id, then `gh api repos/<o>/<r>/actions/jobs/<jobid>/logs --allow-escape-sequences`. Confirm each named file at the head with `git show <head>:<path> | tail -c1 | od -An -c`.

- **`check-pr-authors` has no check name of its own — it runs inside `linux / unit`.** So
  "every listed check is green, the rest are pending" says nothing about attribution. Run it
  yourself on every PR, over the PR's own range:
  ```bash
  python3 scripts/check_pr_authors.py check --base origin/main --head HEAD
  ```
  A commit authored `Asimov Agent <agent@asimov.invalid>` (or `asimov-agent`,
  `github-actions[bot]`, `Hermes Agent`, …) is outside the allowlist and reds the unit job;
  only `Andy Holst <andy.holst@protonmail.com>` and `Asimov Agent <support@docondee.com>`
  are allowed, name AND email. Repair is the gate's own prescription and rewrites no work —
  `git commit --amend --no-edit --reset-author` (author+committer set to the allowed pair),
  `git push --force-with-lease` on the PR's own branch, then prove the tree did not move
  (`git diff <old> <new>` empty) and re-run the check for `OK`. A whole agent fleet can share
  one bad git identity, so check every PR in a batch before believing any of them is green.
- **An author-gate red naming commits that are not the PR's is a range bug, not a rebase.** When CI's
  `guard`/`check-pr-authors` fails and the named shas are `main`'s own merges, do not tell the lane to
  rebase — rebasing onto the newer base is exactly what pulls those commits into the scan. Reproduce the
  **CI shape** and the **PR's own shape** side by side:
  ```bash
  git fetch origin refs/pull/<n>/head refs/pull/<n>/merge
  # CI: PR's recorded base sha .. the merge ref (a pull_request head IS the merge commit)
  python3 scripts/check_pr_authors.py check --base <pr-base-sha> --head refs/pull/<n>/merge   # reproduces the red
  # the range the PR actually owns
  python3 scripts/check_pr_authors.py check --base origin/main   --head refs/pull/<n>/head    # usually OK
  ```
  `ci.yml` passes `PR_BASE = github.event.pull_request.base.sha`, so `<base>..<head>` sweeps everything
  the base branch gained after that sha. The fix is the range start (`mb=$(git merge-base "$PR_BASE" "$PR_HEAD")`),
  which is what `check_pr_authors.py`'s own docstring claims the scan is. Also check the default branch
  before blaming any PR — `git log -6 origin/main --format='%h %an <%ae>'` and
  `--base <old-tip> --head origin/main`: a missing surname there is enough to red every PR at once, and
  re-authoring `main` is a history rewrite that stays the owner's call.
- **A `docs/changes.d/<x>.md` fragment must link an `agent-wiki/<name>.md` note that exists on the
  SAME branch — `check-docs` reds otherwise, and it catches it before you can commit.** The fragment is
  a one-row index entry whose `Record` cell points at an `agent-wiki/` note; `changes-index` asserts that
  note is present, so creating a fragment on a branch that does not carry the note (e.g. you draft a
  change-record on the reviewer's own branch but the note lives only on the PR-under-review's branch)
  fails with `[changes-index] ERROR: docs/changes.d/<x>.md: links agent-wiki/<name>.md, which does not
  exist`. Always run `make check-docs` (or `make changes-index`) over the exact branch before committing
  the pair — a fragment with a dangling note reference is a red gate, not a record. When the note lives
  on another branch, either add the note here too or do not create the fragment; never leave a
  note-less fragment behind. The link target must be `agent-wiki/<name>.md` or `./agent-wiki/<name>.md`
  — the gate's regex anchors on that prefix, so `../agent-wiki/<name>.md` (the natural path when the
  fragment sits in `docs/changes.d/`) fails the link check even though the file exists on the branch.
  Write the path relative to the **repo root**, not to the fragment, and re-run `make check-docs` after
  fixing a `../` link.
- **When your local branch has diverged from the fork ref you mean to update, push to a DISTINCT branch
  — never force over a shared/foreign branch lineage.** A reviewer's record commits often build on
  `main`'s history while the fork branch (`fix/…`, `reports/…`) still carries the earlier review-record
  lineage, so `git push fork <branch>` is rejected non-fast-forward and `--force` would discard the
  remote lineage. The safe move is `git branch <new-name> HEAD && git push fork <new-name>` — a fresh
  ref that carries your commit without rewriting anyone else's — then verify with
  `git ls-remote fork refs/heads/<new-name>`. Confirm ancestry first (`git merge-base --is-ancestor
  <remote-sha> HEAD`); if it is NOT an ancestor, they diverged and a force is the wrong tool.
- **A `pull_request`-triggered gate reads the PR body snapshotted at event-fire — re-running the same run id can NEVER clear a stale-body red; only a fresh `pull_request` event does.** `ci.yml` passes `PR_BODY: ${{ github.event.pull_request.body }}`, which is frozen into the stored event payload when the run is created. Editing the body afterwards and re-running (`gh run rerun`) re-reads the OLD body forever, so the gate reds identically and reads as "the fix did not work". Discriminate before blaming anyone: compare the run's `created_at` (from `gh api …/actions/runs?head_sha=<sha> --jq '.workflow_runs[]|.created_at'`) against the body's `updatedAt`. If every run at the head fired BEFORE the edit and the gate passes locally against the current body (`check_pr_closing.py check --body-file <current> --rev HEAD` → rc=0), the red is a snapshot artifact, not a tree defect. The only remedy is a **fresh `pull_request` event at the same head** — close+reopen by the owner, or a no-op commit — never another re-run and never an amend the squash text does not need. Same class as the CANCELLED rule (a cancelled/superseded run is no verdict, needs a fresh run at a frozen head), but here even a fresh run of the SAME event is insufficient: the event payload itself must be re-fired.
- **`check-quant-catalog` reds every PR when the live Hub search changes** (issue #769).
  Do not let an author fold that data regeneration into a feature/docs PR; it is its own
  change.
- Merge order matters: a docs census refresh and a PR that adds files cannot both be
  "current" — land the code PR first, then regenerate the census.
- **A "green" guard that reads *no checks* as green starves exactly the head it must fix.**
  `scripts/rebase_bot_sweep.py::_checks` answers `(False, False)` for `gh pr checks`'s "no checks
  reported" — and a **conflicted** PR has no checks at all — so an `armed && green` skip (the
  `armed_green_head` shape, #2101/AC7) calls an armed `CONFLICTING` head *"its head is green — the
  merger owns this head"*, while `scripts/auto_merge.py::decide` never merges a `DIRTY`/`CONFLICTING`
  PR: the only lane that could fix it now refuses, permanently. Such a guard needs
  `mergeable == "MERGEABLE"` **and** a concluded green run, not absence-of-red. Prove it through the
  real `sweep()` — throwaway test with `armed_by_pr`, `mergeStateStatus=DIRTY`, `checks_by_pr={num: []}`,
  assert `action == "rebase"` — because a fixture written for the happy path cannot show the
  starvation, and it is the fixture that looks green. Delete the probe afterwards.
- **Moving a workflow-level `concurrency:` onto a job reds the #917 tests.**
  `tests/test_auto_merge.py::_concurrency_block()` parses a **top-level** `concurrency:` mapping, so
  after the block moves under `jobs.merge` both `test_a_later_sweep_supersedes_an_earlier_one` and
  `test_the_sweep_group_is_repo_wide_within_each_outcome_not_per_branch` fail with *"auto-merge.yml has
  no concurrency block at all"* — and the #917 shape (which has starved this board three times) goes
  unguarded with them. Whenever a diff touches a workflow's `concurrency:`, run that workflow's tests,
  not only the ones the PR body names.
- **Grep every `- **Test:**` line a spec scenario cites.** A scenario naming a test that does not exist
  passes `make openspec-validate` (it validates shape, not referents), and `tasks.md` will happily say
  *"Pin both in tests"* while nothing does. `grep -n "<cited test name>" tests/` per scenario; a `grep`
  that returns nothing is a blocker, never a formatting nit.
- **A ticked acceptance box still reds `check-pr-acceptance` unless its `(proven: …)` names `run=<id>`
  or a `command … rc=<n> … <sha>`.** With no CI run at the head, the ref must carry both an `rc=` token
  and a 7–40 hex sha (e.g. `cmd: docker run … pytest … rc=0 head <sha>`), otherwise all four ticks come
  back as `tick-unprovable` and the gate count looks like nothing was written back. Re-run
  `check_pr_acceptance.py check` after the write-back and expect exactly the unticked items as
  violations, with `tick-unprovable` at zero.
