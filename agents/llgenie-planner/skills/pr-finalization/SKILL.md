---
name: pr-finalization
description: >-
  Squash a PR to one commit, refresh title/body, push.
---

# PR Finalization

The user's standing preference is **one fix = one atomic commit**, and a PR is
presented already squashed — never a pile of fix-it follow-up commits that the
merge-time squash patches over. This is the procedure for getting a feature
branch to that presentable, reviewable state. It is distinct from merge-time
squash (covered by the bundled `github` skill's merge section); this runs as a
deliberate step when the work lands, BEFORE the user reviews it.

## Procedure

0. **When the PR was authored by another agent, verify its SCOPE against the
   issue BEFORE finalizing.** "Backing up" someone's work is not just confirming
   it is committed + pushed + has an open PR — read the issue's actual
   requirement and diff the branch against it. An over-broad fix that "works"
   (e.g. a change applied to EVERY call site when only one class of input needed
   it) is still wrong and must be narrowed before it is presentable. When the
   user says "only X should be Y", they mean ONLY X — do not carry the change
   into the rest of the codebase. Narrow the diff, then re-run the affected
   tests, then finalize. A scope correction is a first-class signal to stop and
   re-scope, not to keep pushing the original shape.

1. **Read the branch history first** so no context is lost — a squash discards
   intermediate messages. Capture what each landed commit contributed:

   ```bash
   git fetch origin
   git log --oneline origin/main..HEAD
   git diff --stat origin/main        # confirm the full scope of the change
   ```

2. **Squash with a soft reset** (NOT hard — hard destroys the staged work):

   ```bash
   git reset --soft origin/main
   git commit -F - <<'EOF'
   type(scope): the whole feature in one line

   Body covering the COMPLETE change: what now works, every non-obvious
   behavior change, and what is NOT covered (paths you could not test) so the
   reviewer knows the boundary. Closes #NN.
   EOF
   ```

3. **Force-push WITH the lease guard** so a concurrent push to the same branch
   cannot be silently overwritten. A plain push is rejected — that is expected:

   ```bash
   git push --force-with-lease <remote> feature-branch
   # verify local and remote heads match before claiming success
   [ "$(git rev-parse HEAD)" = "$(git rev-parse <remote>/feature-branch)" ] && echo ok
   ```

4. **Rewrite the PR title, PR body, AND the linked issue body to describe the
   whole squashed change**, not the headline of the first original commit. A
   title/body written early while the branch kept growing only reflects the
   opening commit by the time the PR finishes, and the issue it closes still
   carries the pre-feature scope. Include a `## What` that matches the new commit
   message and an explicit `## Not covered` section:

   ```bash
   gh pr edit N --repo owner/repo \
     --title "type(scope): <whole feature> (#issue)" \
     --body "$(cat <<'EOF'
   <full body covering the entire diff>
   EOF
   )"
   ```

5. **Verify the result is exactly one coherent commit** whose message matches the
   PR title:

   ```bash
   gh pr view N --json commits,title,state
   ```

6. **If a follow-up change is needed after the squash** (a doc fix, a work record,
   a reviewer-requested tweak), AMEND it into the single commit instead of adding a
   second one — the branch must stay one coherent commit:

   ```bash
   git add <changed-files>
   git commit --amend --no-edit
   git push --force-with-lease <remote> feature-branch
   ```

   Re-verify local == remote == PR head after the amend; the sha changes every time.

## Pitfalls

- **A PR whose CI PUBLISHES artifacts cannot be judged from a fork head.** When the pipeline pushes to a registry
  on every `pull_request` run, a fork head carries a read-only token: the job builds, passes its tests, then dies at
  the publish step with `denied: installation not allowed to Write organization package`. That is a permission, not a
  defect in the change — do not "fix" the code for it. Re-head the PR into the BASE repo: push the branch there
  (`git push origin <branch>`), open the PR with that same-repo head (`--head <branch>`, no `owner:` prefix), and
  close the fork-headed PR with a comment naming the denial so the two are not reviewed in parallel. Two traps: (a)
  **check runs are pinned per sha**, so the closed fork run's red checks stay attached to that commit — add one
  commit (empty is fine) before re-heading, or the new PR shows the old reds; (b) a `push` event on a feature branch
  may run NOTHING (many repos scope `on.push.branches` to the default branch), so pushing the branch proves nothing
  by itself — the run that matters is the same-repo `pull_request` one. Read the failing STEP, not the run
  conclusion, before concluding anything about the change.
- **Push to the remote that hosts the PR HEAD, not the remote named `origin`.** In a fork workflow the PR head lives on the fork, and `origin` may point at the UPSTREAM (the repo you cannot push to) while the fork is a differently-named remote (`fork`). A push to the wrong remote either fails or — worse — creates a stray branch on the upstream. Before force-pushing, resolve the PR head's repo: `gh pr view N --json headRepositoryOwner,headRefName` and push to the matching remote (`git push --force-with-lease <fork-remote> <branch>`). Verify the PR head oid advanced after the push (`gh pr view N --json headRefOid`); the API can lag a few seconds, so re-check once before concluding the push missed.
- **A force push invalidates every prior CI run** on the branch — checks on the
  PR show as pending until the fresh run lands. Say so; never claim green from
  the pre-squash run.
- **`gh pr edit` has NO `--title-file` flag** — it rejects it (`unknown flag: --title-file`)
  while `--body-file` IS supported. Pass the title inline (`--title "..."`) and the body via
  `--body-file <path>` when the body is long or generated; write the body to a temp file rather
  than a shell heredoc (which collides with other command-substitution). Verify the edit landed by
  reading it back (`gh pr view N --json title,body`); a failed edit exits non-zero and leaves the
  PR metadata unchanged.
- **`gh pr edit` while the branch is still growing** leaves a title/body that
  only describe the first commit. Rewrite PR metadata as a final step; never
  assume an early edit still matches.
- **Squash loses message-only context** — anything carried only in an old commit
  message dies unless folded into the new body (hence step 1).
- **Ground the PR and issue bodies in the actual diff** — read `git diff origin/main` and the changed sources before claiming behavior in the narrative. A body that asserts "the check runs the engine's `--version` for every engine" is wrong the moment one engine reads a package version instead; verify the per-case behavior (which paths run the binary vs. fall back) and state the exceptions explicitly. The issue body needs the same pass — do not leave the old scope behind as the feature grew.
- **Number the test-suite claims by ACTUAL collection, never by memory.** Stating "`test_x.py` (6)" when the file holds 7 cases (a parametrized test can grow a case without the headline changing) is a visible factual error a reviewer checks. Before writing any "(N)" test-count into a body, run `pytest <file> --collect-only -q | tail -1` and copy the number it reports. Re-collect after any test edit.
- **Do not assert an install/serve/verify chain "all verified" unless your records actually show each step ran THIS change.** "Real host: `make install` → serve → chat → uninstall all verified" is a hard claim; a work record that only proves the install-python-path part does not back it. Either run the full chain and record it, or temper the line to exactly what you verified (which steps, which machines) and mark the un-run steps as CI gates instead of host-verified. Verify the prerequisite model file is actually present before claiming a serve/chat run.
- **Re-align the PR TITLE to the squashed commit message as a final step.** The title written early (or auto-derived from the first commit) drifts from the squashed message once the branch grew; a title that names only the opening commit's scope while the commit message names the whole feature is a visible inconsistency a reviewer will flag. `gh pr edit N --title "<squashed message subject>"` after the squash.
- **A completion/integrity gate that reports "no task-relevant changed path" after a squash is a signal the turn made no new file change** (the squash+push happened in a prior turn), not that the work is undone. Fix it by making a legitimate task-relative change — e.g. update the agent-wiki / work record to document the finalization — and AMEND it into the single commit (step 6), then re-verify. Do not add a second commit to satisfy the gate; that breaks the one-commit invariant.

## Stacked PRs: base the branch on the dependency, and squash against the RIGHT base

When a change depends on another PR's code (e.g. a removal that keeps a module
another PR introduced, or a refactor that imports a symbol a sibling PR adds),
base the branch on that PR's branch, NOT on `main` — otherwise the dependent
code is absent and the change cannot build or test. The PR then stacks: its
diff against `main` includes the dependency's commits until the dependency
merges.

- **Squashing a stacked branch with `git reset --soft origin/main` pulls in ALL
the stacked commits**, not just your own — the single squashed commit then
carries the dependency's work too. That is correct when the dependency is
unmerged (the PR must contain it to be self-contained), but say so in the PR
body: "this branch stacks on PR #X; once #X merges, this PR's diff against
`main` is just the removal." Do not present a stacked squash as if it were a
clean single-feature diff against `main`.
- **When the dependency merges first, rebase the stacked branch onto the new
`main`** (`git fetch origin main && git rebase origin/main`) so the stacked
PR's diff collapses to only its own change, then force-with-lease-push.
- **A stacked PR that becomes obsolete when its base merges** (the base PR
carried the work into `main`) should be CLOSED, not left open: close the PR
with a comment naming the merged PR that superseded it, delete its remote
branch (`git push origin --delete <branch>`), close the linked issue, and
remove the local worktree + branch. Closing a PR is not a merge, so it is
within the agent's remit.

## Rebasing a stale PR onto a moved `main`

A PR that is behind cannot merge, so rebasing is routine — and the dangerous
part is that BOTH success modes lie: a clean rebase can silently revert a
sibling's work, and a conflicted one can be resolved into a tree that parses
badly.

- **`MERGEABLE` (or a rebase that "succeeds") only means git has no conflict — it says NOTHING about whether the tree is a working tree.** A rebase whose conflicts were resolved by a list-union helper can leave the tree broken while git still reports the PR `MERGEABLE`: raw `<<<<<<<`/`>>>>>>>` markers in a file the resolver did not touch (and `git add -A; rebase --continue` happily accepts a conflicted file as resolved), a cron/recipe line that is a CONCATENATION of both sides (`- cron: "41 5 * * *" # … "11 daily 05:11 …"` — not YAML at all), a test file silently DROPPED from the tree, and a test expectation mangled into a union of both sides and dedented. `resolve_list_conflicts.py` is for LIST conflicts; on any other shape it silently does the wrong thing. So before pushing, verify the tree actually holds — not just that git is happy: `grep -rl '<<<<<<<\|>>>>>>>' --include='*.py' --include='*.yml' --include='Makefile' .` (must be empty), `yaml.safe_load` every workflow, `make -n <target>` parses, and the affected tests pass. A force-push of a broken tree re-triggers CI and fails loudly; catch it locally first. When the user says "make sure it holds during the rebase", this is what they mean — do not report `MERGEABLE, pushed` as success.
- **Never `git commit`/`git commit --amend` while a `rebase` is PAUSED on a conflict.**
  While paused, `HEAD` is the upstream commit the branch is being replayed onto — NOT your
  branch tip. An amend then attaches your staged (resolved) tree ON TOP of the upstream tip
  and can inherit the UPSTREAM commit's message, so the branch ends up carrying main's message
  with a mis-parented, wrong-message commit. The correct finish is: resolve, `git add <files>`,
  `git rebase --continue` (that restores your ORIGINAL branch message). If you already amended
  inside the pause, rebuild: find the true feature commit, `git branch -f <b> <feature-sha>`,
  then re-rebase. Detect it by checking the new head's message/subject against the PR's own
  (`git log -1 --format=%B HEAD`) — if it shows a main commit subject you did not write, you
  amended the wrong thing.
- **`Successfully rebased` / `MERGEABLE` / `ahead=1` do NOT prove the branch sits on the NEWEST main** —
  verify reparenting, not just "ahead". A rebase left paused-and-then-amended, or one whose
  update loop touched the wrong checkout, can leave the branch parented on an OLD main tip:
  `ahead=1 behind=1`, merge-base = a mid-history sha while `origin/main` has advanced. Before
  force-pushing, assert BOTH `git rev-list --count HEAD..origin/main` == 0 (behind) AND
  `git merge-base HEAD origin/main` == `git rev-parse origin/main`. Fix a stale parent with a
  second explicit `git -c rerere.enabled=false rebase origin/main`, then re-verify ahead=1 /
  behind=0, markers=0, and the affected tests before pushing.
- **A token-union resolution can drop a test file by placing it AFTER a recipe's filter flag.**
  `test-unit` (and similar list-shaped recipes) can end with a `-k <pattern>` filter; inserting
  the branch's new `tests/test_x.py` token any later in that one line leaves it on the line but
  AFTER the filter, so it is filtered out and never collected — the PR looks wired while the test
  runs nowhere. After a list resolution, confirm the new test path appears BEFORE any filtering
  flag on its recipe line, not merely somewhere on the line.
- **Rebase with `rerere` OFF when the branch was rebased before**: `git rerere`
  replays its *recorded* resolution and prints `Staged '<file>' using previous
  resolution`.  If that recorded resolution was ever bad it keeps coming back.
  Use `git -c rerere.enabled=false rebase origin/main` and resolve by hand.
- **When the rebase conflict lands on a GENERATED file (an OpenSpec `OPENSPEC.md`
  index, a params JSON, a lockfile) regenerate it, do not hand-resolve and do not
  trust rerere.** rerere replays its previously recorded resolution for that file,
  which is stale the moment the sources changed. Re-run the generator from the
  change/source files (`make openspec-index --write`,
  `make generate-engine-params`, ...), `git add` the regenerated file, then
  `git rebase --continue`. The index is derived; its conflict is never a real
  edit to merge.
- **After ANY block-level resolution, assert no DUPLICATE make targets.** When both sides of a
  *target block* were kept, the union can leave the same target defined twice (e.g. `implement-issue`
  from main and from the branch). `make` does not error — it prints `overriding recipe` once among
  thousands of lines and then silently uses the LAST definition, so one side can vanish while CI
  stays green. Check before committing:
  `python3 -c "import pathlib,re,collections;d=collections.defaultdict(list);[d.setdefault(m.group(1),[]).append(n) for n,l in enumerate(pathlib.Path('Makefile').read_text().splitlines(),1) if (m:=re.match(r'^([A-Za-z0-9_./-]+):(?!=)',l))];print({k:v for k,v in d.items() if len(v)>1} or 'none')"`
  Anything listed: merge the two into one (the branch's newer copy plus anything main's has that it
  lacks), drop the other, re-check. Same class as a doubled prose paragraph after a README block
  union — `git diff` it, because no test may catch either.
- **Check the recipe TAB after resolving any Makefile/tabfile list conflict.**
  List-shaped conflicts (a target whose whole value is one long line, e.g. a
  `test-unit` file list) are resolved as the UNION of both sides' tokens — but a
  token-level union (`" ".join(line.split())`) strips the line's LEADING TAB, and
  the recipe then parses as a target: `make` dies with
  `*** target pattern contains no '%'. Stop.` The parse check is
  `make -n <target>`; the test suite never runs, so tests will not catch it.
- **After ANY rebase — clean or not — verify the sibling's content survived.**
  A rebase replays your diff onto main; when both touched the same region git can
  keep one side, so main's newly merged targets/entries can vanish while the
  rebase still reports success. Grep the rebased tree for the symbols the PR you
  were behind introduced (e.g. `git show origin/main:Makefile | grep -c <target>`
  vs your tree) before believing it.
- **Resolve list conflicts with `scripts/resolve_list_conflicts.py`** (a supporting file of
  this skill), not by hand: it keeps main's line, appends only this branch's tokens, drops
  a pytest path that main renamed/removed (reporting the drop), and preserves the TAB. Then
  run the four follow-up checks each time: `make -n <target>`, the list-line count (no
  duplicate), a grep for the branch's continuation line, and the affected test files.
- **A rebase conflict where ONE side carries continuation lines can silently drop them.**
  Resolving `<<<<<<< HEAD` (one long list line) against a side with TWO lines
  (the same list + a `\`-continued second line) by "take HEAD's line, append the
  branch's extra lines" keeps the branch's STALE copy of the shared line as an
  "extra" too, and a token-level union then yields a DUPLICATED list line. After any
  list/tabfile resolution, verify the count, not just the parse: diff the number of
  list lines before/after and grep that the branch's continuation is still there
  (`grep -c '^\t<first-expected-token>'`). `make -n <target>` still parses with a
  duplicate line, so the parse check does not catch it — and a dropped continuation
  line silently removes targets from the `.PHONY`/help list the branch added.
- **When rebasing a RENAME/refactor PR, main may have added files that still use
  the OLD name — the rename guard test catches them, and you must update them as
  part of the rebase.** A rename PR ships a guard test that fails on any live file
  naming the old module. If main merged a new test/script (e.g. a feature that
  landed while the rename was open) that still imports the old name, the rebase
  applies cleanly but the guard test goes red. Run the rename guard after the
  rebase, update the newly-merged files to the new name, and commit that as its
  own fix commit — it is a real cross-PR interaction, not a rebase artifact.
  Rebuild the renamed module from main's version (so it keeps main's new work)
  plus the rename's edits, rather than carrying the branch's stale copy forward.
- **Do not try to `cp` the final resolved file into a multi-commit rebase.**
  The later commits re-modify it and conflict again. Instead replay as one step:
  `git reset --hard origin/main && git cherry-pick -n <c1> <c2> <c3>`, take the
  verified content for the conflicted files, then a single `git commit` — which
  also delivers the one-atomic-commit invariant directly.
- **Keep a verified reference tree and diff against it.** A scratch worktree with
  the branches merged and the gates run is the authority for what the resolution
  should be; `diff <file> ../<scratch>/<file>` being empty is the proof, and any
  remaining difference is either the sibling PR's content (fine) or a defect.
- **A rebase that drops a commit with `patch contents already upstream` (or leaves an
  empty diff) means the PR was already merged** — do not write "closing as superseded".
  Check the PR's real state first (`gh pr view N --json state,mergedAt,mergeCommit`), and
  note that `gh pr close` refuses with *"can't be closed because it was already merged"*,
  which is the tell. A narrow-context guess ("its change is in main, so it must have been
  cherry-picked") reads badly in a public comment; verify, then say what happened.
- **When iterating several PRs, resolve each worktree path CORRECTLY or the loop silently runs in the wrong checkout.** `git worktree list` prints the branch in a bracketed third column (`...  [refs/heads/x]`), so an awk match on `$3 == "refs/heads/x"` never fires; the fallback then `git worktree add`s a NEW worktree at a guessed path, the `cd` into it fails, and every subsequent command in the loop runs in the MAIN checkout — rebasing `main` (a harmless no-op) and pushing nothing. Two guards: (a) let `git worktree add <path> <branch>` fail loudly when the branch is already in use (it errors `already used by worktree at ...`) and use the path it names, rather than guessing; (b) after any push, verify the push LANDED by comparing the PR head to your local head — `gh pr view N --json headRefOid` must equal `git rev-parse HEAD`. A push from the wrong checkout reports `Everything up-to-date` and does nothing; that is a silent no-op, not success.
- **A workflow test that only greps for substrings will not catch a YAML syntax error — parse the file.** A step name containing `: ` (colon-space) inside an unquoted scalar breaks the whole workflow (GitHub rejects it: the run shows ZERO jobs), and a test asserting `"cron:" in text` / `"secrets.X" in text` passes anyway, so the broken file merges. Any test that validates a `.github/workflows/*.yml` must `yaml.safe_load` it (and assert it parses) in addition to the substring checks; a grep-only test is a false green.
- **When a PR's whole purpose is moving cron schedules, the red tests are the ones pinning the OLD minutes — update them, don't chase a regression.** A schedule-change PR (unique slots per bot) fails exactly the tests that assert the previous `cron:` values; the workflow files themselves are usually fine (verify no duplicate `schedule:` block from a block-union). Update the expectations to the new minutes with a comment pointing at the issue, re-run, and move on.
- **Before building a feature, check whether an existing bot PR already covers the same issue — two PRs for one issue is a duplicate, not parallel work.** When a bot's PR and yours implement the same issue with different values, they cannot both merge; pick the one that carries the guard test that prevents the whole class (a test asserting no two workflows share a minute beats a PR that merely uses unique minutes with no test), and close the other as superseded. Flag the overlap to the user rather than silently proceeding.
- **Re-verify with the repo's own gates after the rebase**, not just tests:
  `make -n <target>` (parse), the repo's structural checks, the OpenSpec
  validator, and the affected test files. Then `git push --force-with-lease` and
  re-read `gh pr view N --json mergeable,mergeStateStatus`: the expected
transition is `CONFLICTING/DIRTY` → `MERGEABLE/BLOCKED` (BLOCKED = review still
required; that is the normal end state — never merge it yourself).
- **A fix that lives in a SIBLING commit (not the feature commit) is silently dropped when only the feature commit is rebased onto main.** When a PR's branch is rebuilt by cherry-picking/rebase of just the feature commit (e.g. another session rebases it onto a newer `main`), any fix that was in a separate follow-up commit — a `secrets-in-run-block` guard fix, a lint fix — does not come along, and the repo's guard goes red again on the new head. After ANY rebase of a PR onto main, re-run the repo's own guard scripts (`check_secret_output`, wiring, lint) on the NEW head, not just the tests; a guard that passed on the old branch can fail on the rebased one for exactly this reason.
- **A `--force-with-lease` rejection (`stale info`) means the remote head moved — inspect before force-pushing over it.** The lease only guards against a concurrent push; when it fires, someone (often another agent session) has already rewritten the branch — e.g. rebased it onto a newer `main` and pushed. Do not force-push your old history over theirs. Read the new head first (`git ls-remote <fork> <branch>`), check whether it is your work evolved or a different shape, and build your change on the NEW head (new worktree at that oid, re-apply your edits, push with a lease on the new oid).
- **A passing `--force-with-lease` does NOT prove no other session is on the
  branch — one can push between your fetch and your push and still be overwritten.**
  The lease guards only against a changed advertised head; when the interleaving
  push reused a head you already knew (or a fetch advanced your remote-tracking
  ref), the force-push lands and silently replaces the concurrent commit. After
  any force-push of a shared PR branch, read who wrote it:
  `git reflog show origin/<branch>` — each `update by push` entry is a writer; a
  sha YOU did not create means another session is also working the branch.
  Preserve any commit you overwrote as a backup branch
  (`git branch -f backup/<label> <sha>`) so that work is not lost, and report the
  collision.
- **Audit a fleet of open PRs for behind-ness and conflicts WITHOUT merging or touching branches:** `git rev-list --count fork/<branch>..origin/main` (how far behind) and `git merge-tree --write-tree origin/main fork/<branch>` (conflict count — lines starting `CONFLICT`). Fetch all heads first (`git fetch fork 'refs/heads/*:refs/remotes/fork/*' -f`). This yields a per-PR `behind / conflicts / mergeable` table in one pass, so you can report the whole queue's state and spot which PRs need a rebase before any of them is touched.
- **Do not build a commit message as a heredoc inside a Python f-string passed to `subprocess.run(..., shell=True)`** — the `<<'EOF'` heredoc consumes the rest of the command and the commit silently never runs (empty `git log`), while the push still executes and fails on the lease. Write the message to a temp file and `git commit -F <file>`, or pass `-m` args, when constructing a commit message programmatically.

- **Judge a credential/approach change on the branch by what the REAL pipeline
  does, not by how coherent the diff looks.** A companion session can make a wrong
  credential choice look deliberate — workflow + docs + tests + the generated
  index all updated to match. When the change decides WHICH token publishes/pushes,
  do not accept it on coherence: dispatch the actual workflow from the branch
  (`gh workflow run <wf> --ref <branch>`) and read the publish/push job's output.
  A token the pipeline's own push probe rejects (`permission_denied ... does not
  match expected scopes`) is wrong however complete the surrounding change is;
  revert the choice to the credential that measurably works.
- **After you REVERT or change direction on a piece the PR already described, the
  PR body and issue body are now wrong — re-align and verify by read-back.** A
  body praising the rejected approach while the branch ships the working one is a
  visible defect a reviewer flags. After any direction change, update body AND
  issue body to the new reality, then read the body back and grep for the
  discriminating claims (branch workflow shows `GHCR_TOKEN: ${{ github.token }}`
  with no `secrets.`; the body must say the default token and why the alternative
  fails).

## Every PR body ends with `closes #<issue id>`

The user's standing rule: a PR body MUST end with the deliberate closing
keyword `closes #<issue id>` (not a bare `#N` mention) so the PR ↔ issue link
is unambiguous. Apply it to every PR you open or edit, and mirror it in any
worker/agent prompt that instructs opening a PR.

- **When you APPEND a section to an existing body** (e.g. a follow-up change
  added after the first push), the closing keyword is no longer the last line —
  the appended text lands after it and the body now ends with the new section.
  Re-append `closes #<issue id>` as the final line after any body edit, and
  verify with `gh pr view N --json body -q '.body' | tail -1` (or
  `.rstrip().endswith("closes #N")`). The GitHub issue link survives a
  mid-body mention, but the standing rule is about the body's ENDING, so the
  keyword must be re-placed last.
- **A follow-up PR with no issue of its own must NOT end with `closes`.** When
  the PR is a follow-up whose referenced issues close with their OWN PRs (e.g.
  a CI-budget hardening that refs the two bot issues, each closed by its own
  feature PR), ending with `closes #N` would be a FALSE link — it would claim
  to close an issue another PR closes. End with `Refs #a, #b` instead and add a
  short "Why this does not end with `closes`" note in the body so a reviewer
  sees the omission is deliberate, not a missed keyword. The rule's purpose is
  an unambiguous PR↔issue link; a false `closes` breaks that as surely as a
  missing one.

## Not merge-time squash

Do not treat this as a substitute for the maintainer's squash-merge, and do not
merge anything yourself — delivery stops at the clean, reviewable PR.
