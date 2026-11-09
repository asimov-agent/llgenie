# Proving a fix, repo pitfalls, and versioning this skill

Extracted from SKILL.md to keep the always-on body small; load it when you are about to
prove a fix, hit one of these traps, touch `.hermes/skills`, or version this lane's own
profile under `agents/<profile>/`.

## Reading a CI failure without the runner's log stream

`gh run view --log-failed` answers "still in progress; logs will be available when it completes" and
`gh run view --job <id>` returns 0 bytes with the pinned token — a CLI guard, **not** an API limit. Two
gotchas: `gh run view` needs a git-repo cwd (or an explicit `--repo <owner>/<repo>`) or it errors
instead of reading, and it gates logs on the WHOLE RUN — a cell that already concluded `failure` still
reads "run <id> is still in progress; logs will be available when it is complete" while ANY sibling cell
of the same run is live, even though one job never depends on another. The API serves the per-job log at
any time, regardless of the run's overall status:

```bash
gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' > /tmp/job.log
grep -m1 'not published yet' /tmp/job.log | cut -c1-30     # first poll
grep 'not published yet' /tmp/job.log | tail -1 | cut -c1-30   # last poll -> budget actually spent
grep -c 'not published yet' /tmp/job.log                  # 90 polls x 20 s = 30 min, confirmed
```

That timing is what separates "the wait gave up too early" from "nothing ever produced the
artifact": 90 polls across exactly 30 minutes means the documented budget was honoured and the
producer job never ran — an ordering/capacity defect (#893), not a bad tag.

## Proving a red is NOT a regression (structural, before you blame the rebase)

After you rebase a branch onto a newer `main`, the first CI at the new head can show a job red that was
"green before". Before you treat it as a rebase regression, prove the job EVER ran at the prior head:

```bash
gh api repos/<o>/<r>/commits/<prior-sha>/check-runs --jq '.check_runs[].name'
gh api repos/<o>/<r>/commits/<new-sha>/check-runs   --jq '.check_runs[].name'
```

If the prior head lists only three or four checks (`guard`, `holds`, `scope`) it never materialized the
`linux/…` matrix at all — the matrix first dispatched at the NEW head, so **no flip is possible and there
is no regression to attribute.** This is a claim about substance, not a story: report the two check-run
counts (e.g. 4 vs 15), not "it was green before".

**A `linux / unit` or `linux / openspec` red is often the SAME intended `openspec-tasks-check` gate, not a
test failure.** `make ci-unit` runs `issue-bot-gates → openspec-tasks-check`, so an unticked openspec box
reds the unit JOB while the unit SUITE is fully green. Read the job log's two halves before writing
"unit failed": grep the `N passed` summary (e.g. `2942 passed`) AND the failing step marker
(`[openspec-tasks] FAIL <change>: unchecked task checkbox(es) at lines [...]` → `make[1]: ***
[Makefile:659: issue-bot-gates] Error 2` → `ci-unit Error 2`). The `scope` check and `linux/openspec` red
the same gate. When all three point at the identical `openspec-tasks` line, it is ONE intended box cascade,
no defect — say so and name the unticked boxes; never read `job=failure` as `tests failed`.

The OTHER false alarm on the same job is the **import-roots ratchet** (below). So `ci-unit` exit 2 has
three classes of cause, and the pytest `N passed` line rules out a real test failure fast:

1. Real test failure — grep `^FAILED`; not the common case for a PR that only added files.
2. `openspec-tasks-check` box cascade — an intentionally unticked box (previous paragraph).
3. `check-import-roots` ratchet — a NEW test file's own bootstrap exceeding the recorded baseline.

**A `ci-unit` red whose pytest section says `N passed` is NOT a test failure — read the step AFTER
pytest.** `make ci-unit` runs several gates; the common false-alarm when you add a test file is
`make check-import-roots` (issue #1101 ratchet): a test that bootstraps its own
`sys.path.insert(0,'scripts')` + a bare `import <script>` (the suite-wide pattern) pushes both counts
past the recorded `tests/fixtures/import-roots-baseline.json` (bare and sys-path) and is refused with
"a NEW import root is refused". The baseline is a MEASUREMENT, not a constant — the guard's own docstring
prescribes re-recording it at what the branch actually produces, which is the correct fix, NOT editing
the test to dodge the import:

```bash
python3 scripts/check_import_roots.py report --update   # re-record bare + sys-path from THIS tree
python3 scripts/check_import_roots.py ratchet           # rc 0 proves the gate now passes
```

Commit the re-recorded baseline in the SAME commit as the new test file (it is a test fixture, not a
behaviour change, so it owes no `docs/changes.d` fragment), and confirm the diff is confined to the
baseline JSON. Diagnose which step failed with
`gh run view <run> --log-failed | grep -iE "pytest|passed|failed|Error"` — the failing STEP is the last
non-test command before the `make[1]: *** Error 1` line, not the pytest summary.

## Proving a fix, and cutting the branch it ships on

**Work in a worktree, never in the primary checkout.** `$HOME/repository/git/llgenie` is the
shared builder workspace other lanes treat as `origin/main`; commits parked there on a feature branch
make every other lane's tree ambiguous. Do:
`git worktree add ../llgenie-wt/<slug> -b <slug> origin/main`, work there, and keep the primary
directory on `main` and clean. **Push the branch as soon as it has one commit** (fork is fine for a
branch that needs no publish): an unpushed branch is a single copy on one disk, and a reviewable one
needs a remote to point at.

**A completion/integrity check reads the PRIMARY checkout's working tree, not your
`llgenie-wt/<slug>` (or `/tmp`) commits.** A change committed only in a worktree can read as "no
task-relevant changed path" to a guard that diffs the primary directory — the worktree commit is real
but invisible to it. When such a guard fires, also make the SAME content visible in the primary: apply
the edit to the primary's copy of YOUR OWN files as an UNSTAGED working-tree change (never `git add`
or commit there — other lanes' staged work lives in that index), and regenerate the derived JSON in the
primary so it is byte-identical to the committed branch (`sha256sum` both to prove it). "Keep the
primary on main and clean" means no stray COMMITS/branches there; an unstaged edit to a lane's own
file is the guard-visible evidence, and the branch commit stays the deliverable.

The repo's standard is "the new test fails on the parent, passes on the fix", and the checkout
you inherit is usually sitting on somebody else's PR branch. Both have a recipe.

1. **Isolate the change** — never commit onto an unrelated branch:

   ```bash
   git stash push -u -m "<what>" -- <files>
   git checkout -b <fix-slug> origin/main
   git stash pop
   ```

   Repeat per concern: one branch per defect, so a PR body and a reviewer see one thing.
2. **Prove the test is a real gate** — restore the parent's file, run ONLY the new test, put
   the fix back:

   ```bash
   cp scripts/<f>.py /tmp/fix.py && git show HEAD:scripts/<f>.py > scripts/<f>.py
   env HOME="$HOME" RUNTIME=docker PATH="$HOME/llama-gguf-tools/.venv/bin:$PATH" \
     python -m pytest tests/test_<x>.py -q -k <new_test>
   cp /tmp/fix.py scripts/<f>.py
   ```

   A test that passes both ways proves nothing; the failing-on-parent run is the evidence the
   PR body quotes. The repo's own venv is required — bare `python3` has no `pytest`.
3. **Multi-line Python/YAML edits**: rewrite with `python3 - <<'PY'` doing an
   `assert old in text` then `text.replace(old, new, 1)`, and `ast.parse` afterwards. The
   `patch` tool mangles long block replacements in this tree.

## Shipping a branch another lane rebuilt

When your branch is no longer the one you pushed — the head moved, or the diff suddenly carries
other people's files — **stop**: a rebuilt branch is read-only until whoever dispatched you says
otherwise. Asking costs one message; a force costs someone else's commits. Once authorised:

1. `git fetch <remote> <branch>` — the head you rebase onto must be the one that exists right now.
2. Rebase ONLY your own commits: `git rebase --onto <their-head> <your-old-base>`. A plain
   `git rebase` replays their commits on top of themselves and produces a conflict storm.
3. Prove the scope: `git diff --stat <their-head>..HEAD` must list your files and nothing else.
4. Check no run is live at that head: `gh run list --branch <ref> --json status,headSha` and wait
   for `completed`. A licence covers *what* to push, never *when*.
5. Push once, leasing the sha you just fetched:
   `git push <remote> HEAD:refs/heads/<b> --force-with-lease=refs/heads/<b>:<fetched-sha>`.

Never `--force`, never rewrite their commits, never re-push "to make it clean": the deliverable is
one fast-forward from their head.

**Rebasing a STACK of your own PRs onto a newer main.** When a PR's branch carries another of your
PRs' commits (a stack), a plain `git rebase origin/main` replays them together and drags the other
PR's diff into this one. If that commit is being shipped by its OWN PR, drop it here and reapply only
yours: `git rebase --onto origin/main <the-other-commit-sha>` — the one case where `--onto`'s base is
a commit you are deleting, not a remote head. Verify it worked with `git log --oneline origin/main..HEAD`
(only your commit remains) and `git diff --stat origin/main..HEAD` (only your files), run that PR's own
tests at the new head, then push each branch once with `--force-with-lease` against its freshly fetched
remote sha. Main advancing past the sha you cut from means the head sha WILL change — report the new sha
and confirm the PR is still `MERGEABLE`; "it stayed <old-sha>" is only true when main did not move.

**Your OWN branch rebased onto a moved `main`: `--onto <new-main> <old-merge-base>`, never a bare
`--onto <new-main>`.** When `main` advances and you replay your own commits, the upstream arg is the
branch's OLD merge-base (e.g. `git rebase --onto b747440d 52b21a42`); omitting it (or passing the same
sha twice) replays nothing and leaves you silently on the old base. Prove the move before the lease:
`git rev-list --left-right --count <new-main>...HEAD` must read `0 N` (zero behind, N ahead) and
`git merge-base --is-ancestor <new-main> HEAD` must return 0. A clean replay that shows `ahead=N/behind=0`
with `merge-base == main` is the proof the rebase actually landed on the new tip, not a no-op.

## Re-shaping a branch two lanes co-own: cherry-pick a range, temp refs, ONE lease

When a shared branch carries both lanes' commits and the agreed fix is a base move plus every
carried commit reapplied, drive the reshape with **`git cherry-pick <old-base>..<tip>` rather than
`git rebase --onto`**. A bare `git rebase --continue` can hang even with `-c core.hooksPath=/dev/null`
— the failure lives in the interactive-rebase resume state, not the hooks, and reproduces in a fresh
worktree. Cherry-pick of the whole range applies-or-stops per commit and runs no interactive-resume
resume step, so it both sidesteps the hang and proves itself: `git rev-list --count <new-base>..HEAD`
is genuinely "all N carried" because cherry-pick stops for resolution instead of silently skipping.
Resolve each conflict toward the intended net tree, and leave generated tables (BOTS, a matrix) to ONE
generator regen at the end rather than per-commit hand-edit.

- **Two lanes each holding local-only commits cannot compose a shared head.** A commit on your disk is
  not reachable by the other lane until it is published: `git push <remote> <sha>:refs/heads/tmp/<slug>`,
  the other lane `git fetch` + `git cherry-pick $(git rev-parse FETCH_HEAD)`, then delete the temp refs
  once the final head is pushed. Never keep the authoritative routing commit local-only when a co-push
depends on it — it blocks the whole merge on a sha only you can see.
- **Verify the NET TREE before the lease, not just that the range applied.** Before the single
  `--force-with-lease=<branch>:<freshly-fetched-sha>` (the remote sha is the only thing you lease):
  `git merge-base --is-ancestor <base> HEAD`, the commit count above base, the marker/workflow/membership
  set on the HEAD blob (`git show HEAD:<file> | grep -c`), and the author gate at the base. When two
  parallel complete heads exist for the same reshape, consolidate on the one carrying the authoritative
  routing commit — do not push the reproduction just because it is green, and do not double-apply the
  routing by re-cherry-picking a reproduce of it.

## Squashing a branch's commits into one atomic commit

When the owner wants a PR's several fixup commits collapsed into one clean commit:

1. `git rev-list --count <base-sha>..HEAD` first — know how many you are collapsing. A stray word in
   the range arg (`<base>..HEAD echo`) makes git answer `fatal: ambiguous argument 'echo'`; keep the
   range arg to the two refs.
2. `git reset --soft <base-sha>` — moves `HEAD` to base and leaves the ENTIRE net change staged; nothing
   is lost and the worktree is untouched (no churn, no stash).
3. Commit once — `git commit -F /tmp/msg.txt` (or `-F -` with a `<<'EOF'` heredoc) — then confirm with
   `git log --oneline -1` (one commit) and `git diff --stat <base> HEAD` (the intended file set + counts).
4. `git status --short` must be empty; a leftover means a change was untracked and the soft reset did
   not stage it.
5. Force-push leasing the sha you READ BACK from the destination remote THIS turn: `git ls-remote <url>
   refs/heads/<branch>` → `git push --force-with-lease=<branch>:<that-sha> <url> HEAD:refs/heads/<branch>`.
   Never lease a local remote-tracking ref or a remembered sha — both are stale and the push rejects as
   `stale info`, or worse, clobbers a head that moved.
6. Read the branch and the PR head back (`git ls-remote <url> refs/heads/<branch>` and `gh pr view --json
   headRefOid`) so the report quotes the NEW sha you created, not the one you replaced.

## Before you push: the branch may already be repaired

Two lanes dispatched at the same red head WILL both produce a fix. Measured: one worker rebuilt the
branch on `origin/main` (`0ff0f71`) while another lane had already pushed an equivalent repair
(`78c1689e`) — same subject, different parent, non-ancestor commits. Pushing the re-cut would have
`cancel-in-progress`'d a matrix with 14 greens in flight for a tree that already existed.

```bash
git fetch fork --quiet; git ls-remote fork refs/heads/<branch>   # where the head really is
gh pr view <n> --json headRefOid --jq .headRefOid                # and what the PR thinks it is
git show --stat <remote-head>                                    # is YOUR change in it?
```

If the remote head already carries the change, change nothing: verify it (targeted tests at that
sha) and report the verdict. Spend the local suite on the PUSHED tree, not on your duplicate.

**Verify that content LANDED only against a freshly fetched ref.** `git show origin/main:<file>` off a
stale local remote-tracking ref serves the PRE-merge tree, so it can report your fix "still absent" (or an
old defect "still present") after main already carries the squash — a false verdict a lane then acts on.
`git fetch origin main` first and treat `gh api …/git/refs/heads/main --jq .object.sha` as the
authoritative tip to compare the local ref against before quoting any content check.

## Local `make ci-unit` is not the verdict to wait for

- It runs ~14 600 tests including LIVE network reads (Hub/GitHub downloads in `tests/test_trend_pick.py`)
  and takes 75 min-2.7 h when the fleet has several suites on one host. Each `pytest-timeout`
  faulthandler dump ("Timeout (0:05:00)!") is a stack snapshot, NOT a failure — the test keeps going.
- The authoritative verdict is the `linux / unit` JOB:
  `gh run view <run> --json jobs --jq '.jobs[]|select(.name=="linux / unit")|{status,conclusion}'`.
  A run whose overall `status` is `queued` can still have that job `completed/success` — quote the job.
- A suite interrupted mid-run leaves `make` at `Error 130`; grep `^FAILED` in the log, never trust the
  exit code of a run you stopped.
- **Run a long local gate in a TRACKED background process with `notify_on_complete`, never in a
  foreground call.** `make ci-unit` (and `make render-trend-list-matrix` + its matrix test) exceed the
  180 s foreground tool cap, so a foreground run is killed MID-suite and you cannot tell "still
  compiling" from "crashed" — the log just stops. Start it `background=true, notify=true`, then check
  the sentinel with a SEPARATE short call (`grep CI_UNIT_EXIT /tmp/ci-unit.log`), not a `sleep` poll.
- **Do not poll a background job with a sleep loop inside `execute_code` — the cell has a ~300 s cap
  that kills the kernel and LOSES all state** (variables, imports, the poll counter). A `for …
  time.sleep(15)` waiting on a 10-minute build dies at 300 s and reports a timeout, not the run's
  verdict. Poll with a fresh short `terminal` call (`grep <sentinel> <log>`), or wait the fixed time in
  the foreground and read the log once; keep `execute_code` for branches you can finish in seconds.
- **A serve-readiness timeout is a BUDGET, not a gate. Scope a larger budget to the slow arch instead of
  weakening the assertion.** The engine-smoke default `--timeout 600` is the cold-boot readiness budget; a
  GPU-less `cpu` cold boot can cross it by ~1 s while `cuda`/`rocm` finish well inside. Raise it for `cpu`
  only (`make test-engine ARCH=cpu → --timeout 1200`) and keep the default elsewhere — the image must
  still ANSWER the OpenAI API, so this is more time to become ready, never a relaxed pass. Prove the recipe
  renders the right value per arch with `make -n test-engine-stage ENGINE=<id> ARCH=cpu TEST=serve` before
  pushing; a per-arch budget in the Makefile needs no new openspec change when `check-docs` still validates
  the documented target.

**Freeing a suite you no longer need** (its container's PID 1 is root-owned): `kill -TERM 1` is
ignored, and `docker kill` / `sudo` / `rm -rf` are refused by the harness in single-query mode.
`docker exec <container> kill -INT 1` works (pytest aborts). A leftover worktree's root-owned
`__pycache__` cannot be deleted as the user — `git worktree remove --force` still unregisters it and
the scratch dir self-prunes after 24 h; say so instead of leaving an unmentioned 14 MB.

## Two identities may author a commit

`scripts/check_pr_authors.py` accepts exactly `Andy Holst <andy.holst@protonmail.com>` and
`Asimov Agent <support@docondee.com>`; every other name/email pair reds the PR (`LLGenie Pipeline
Maintainer`, `github-actions[bot]`, `Hermes Agent`, a bare `andyholst`). **The display name is matched as an
EXACT string, so a run of two allowed names is still red**: `Asimov Agent / Mr. Asimov
<support@docondee.com>` (the right email, a plausible-looking author) is REJECTED because
`Asimov Agent / Mr. Asimov` is neither allow-listed name — author as exactly `Asimov Agent` OR
`Mr. Asimov`, never a concatenation of the two. Re-author in the same push
that fixes the code — `git commit --amend --no-edit --author="Asimov Agent <support@docondee.com>"`
— or the PR stays red for a second reason nobody is working on.

**The gate reads EVERY commit in the base..head range, so ONE commit with the wrong email reds the
whole PR** — the branch can be green for six commits and a seventh made under a wrong local config
(`agent@asimov.dev` instead of `support@docondee.com`) turns the guard red on its own. Verify BEFORE
the push, not after the CI red:

```bash
# set the identity at repo/worktree level first — a plain `--author` only fixes ONE commit
cd <worktree> && git config user.name "Asimov Agent" && git config user.email support@docondee.com
python3 scripts/check_pr_authors.py check --base <base-sha> --head HEAD    # rc=0 == every commit allowed
```

When the offending commit is the tip, `git commit --amend --reset-author --no-edit` re-stamps it from
the now-correct config; when it is buried, **`git rebase --reset-author` alone re-stamps only the
replayed commit at the TIP, not the earlier commits in the range** (doing `git rebase --reset-author`
over a 5-commit branch leaves the 5 buried commits with the old author and only fixes HEAD). The
reliable non-interactive bulk fix is an `--exec` amend driven by the author/committer env, which
re-stamps EVERY replayed commit:

```bash
GIT_AUTHOR_NAME='Asimov Agent' GIT_AUTHOR_EMAIL='support@docondee.com' \
GIT_COMMITTER_NAME='Asimov Agent' GIT_COMMITTER_EMAIL='support@docondee.com' \
  git rebase origin/main --exec 'git commit --amend --no-edit --reset-author'
```

Then read back `git log --format='%h %an <%ae>' origin/main..HEAD` and confirm EVERY line is the
allowed identity before pushing.
An author-only amend changes the commit sha (content identical) — force-push to BOTH the head repo
(the fork) AND the mirror, and re-dispatch the proof run at the new head, because the old run's sha is
now superseded.

**A scope job that fails ONLY at `make ci-openspec` is the intended box-4 cascade, not a second
defect** — the `no unchecked task` check reds because the PR intentionally holds a box unticked until
the proof is green. Read the job's step list: if guard/lint/docs/wiring/issue-bodies pass and only
`ci-openspec` fails, that red is expected and needs no fix. Only a step outside the intended cascade
(a `check-pr-authors` guard, a lint failure) is a real defect. Report which signs are the cascade and
which is real, rather than handing the planner three undifferentiated reds.

## A rename is finished only when the tree has no old name

Renaming a test node, a make target or a flag updates the three places people remember (the
definition, the fixture that lists it, the recipe that runs it) and then leaves string references
in assertions that COMPARE against those lists. Sweep the whole tree for the old identifier before
calling it done — `*.py`, `*.json`, `*.yml` and the `Makefile`:

```bash
python3 - <<'PY'
import pathlib
old = "test_old_node_name"
for p in pathlib.Path(".").rglob("*"):
    if p.is_dir() or ".git" in p.parts or (p.suffix not in {".py", ".json", ".yml"} and p.name != "Makefile"):
        continue
    if old in (t := p.read_text(errors="ignore")):
        print(p, t.count(old))
PY
```

A leftover reads as a logic bug ("the roster does not contain this node") when it is a half-done
rename, and the fix belongs in the same commit, not in a report.

## Pitfalls

- **A background launcher's `rc` is the SHELL's last command, never the wrapped program's.** A script
  that ends in `exit 0`, or whose notification is `echo "rc=$?"` after the redirect, reports `rc=0`
  on a failed run — and a `> log 2>&1` that never ran leaves a **0-byte log**. Both look green in a
  notification. Read the WRAPPED artifact, not the launcher's exit: check the log is non-empty and
  grep its real verdict (`grep -m1 '== ' /tmp/repro.log`), and treat "rc=0 + empty log" as "never
  ran", not "passed". Re-fired stale launchers from an abandoned experiment each report their own
  `rc=0` — they are noise on a superseded path, not new evidence; identify the ONE live experiment
  and ignore the rest instead of re-analysing each notification.

- **The picker does not take a bare path as its model argument.** `llgenie /path/to/x.gguf`
  answers `No model matches '<path>'. Use --list`. Pass a substring (`llgenie Ternary-Bonsai`)
  or the explicit file flag (`--model-file /path/to/x.gguf`).
- **`--model-file` labels a LOCAL file with a REGISTRY model name and can pair it with the
  wrong engine.** A 0.5B GGUF was reported as the registry's flagship model and handed to
  SGLang, which wants HF safetensors, not a GGUF. Pin the engine with `--engine <id>`
  whenever you serve a local file, and treat the printed `Model :` line as unverified until
  it matches the file. A format/engine mismatch here is a picker defect to report, not a
  reason to hand-tune a command.
- **A GGUF needs a GGUF engine.** SGLang/vLLM/TensorRT-LLM serve HF weights; llama.cpp
  (and its forks), Ollama and the own-checkpoint engines serve GGUF. Passing a `.gguf` to a
  safetensors engine fails after a long load, not at parse time.
- **The `.gguf` extension does not say WHICH GGUF engine can load it.** A fork-only tensor
  type (Prism's `PQ2_0 = 142`, `PTQ1_0 = 143`) makes stock llama.cpp refuse the file at load
  (`invalid ggml type 142`) — discovered only after the container started, which reads as a
  hang. Read the header's tensor types (`model_engine_pick.gguf_tensor_types`, no dependency)
  before pairing a GGUF with an engine; the file's bytes decide, not its suffix.
- **Re-applying a patch blindly duplicates it.** After a revert or an edit round-trip the fix
  may already be in `HEAD`: check `git show HEAD:<file> | grep -c '<marker>'` before writing it
  again, and use `git checkout -- <file>` to get back to `HEAD`. Two copies of the same block
  still pass the tests, so nothing catches it.
- **When you move a production call site to a different seam, every test that monkeypatches the
  OLD seam silently records the WRONG call.** A build helper that streams via `_sh_live` instead
  of `_sh` (run_live policy), or a wrapper renamed `run`→`run_live`, leaves a test that patched
  `ei._sh` capturing the next unrelated subprocess (e.g. the `buildx inspect`) instead of the
  command under test — the recorder's `calls[-1]` is the wrong command and the flags asserted are
  never exercised, so it reds or (worse) passes against a proxy. Before changing the seam, grep
  the test tree for it (`search_files pattern='_sh_live'`, `grep -rn '"_sh"' tests/`) and widen
  every recorder to set BOTH seams (`monkeypatch.setattr(ei, "_sh", rec)` and the `_sh_live` twin).
  Keep the assertions UNCHANGED — you are capturing the real call, not weakening the test; an
  assertion relaxed to match the proxy is the failure mode this rule exists to prevent.
- **A stale file IS the evidence — copy it before you fix it.** When a fault is proven by a file on
  disk (a stale launcher, a hand-edited params file, a drifted lockfile), `cp` it to `/tmp` (or the
  scratch dir) FIRST, then repair the host. Fixing first destroys the specimen a reviewer wants
  cited, and reconstructing it later is a reconstruction, not an observation. Two proofs are cheap:
  the artifact that failed, and the clean run after the fix.
- **An image tag hashes FOUR inputs, not just the params**: the variant's params, its committed
  Dockerfile, `containers/engines/entrypoint.sh` and `scripts/engine_runner.py`. Editing the runner
  (or the entrypoint) recomputes every engine's tag, so a launcher installed from another checkout
  legitimately reads as stale — classify drift as "pin moved" vs "one of the other three inputs
  moved" before blaming a pin.
- **A merged PR's branch is dead — push there and you have shipped nothing.** Once the PR is merged,
  its head is history: a commit pushed onto that branch appears on no PR, no run, and no reviewer's
  screen. Check `gh pr view <n> --json state` before a late push; if it says `MERGED`, cut a fresh
  branch from the current `origin/main`, carry the single commit over, open a new PR and arm it. The
  same applies to a base: an instruction that names "the branch under PR #N" is only valid while #N is
  open — verify, because a superseded PR's branch can be replaced by another one entirely and the live
  tree may sit on a third.
  **Read merge state from the RIGHT field of the RIGHT surface.** REST `gh api .../pulls/<n>` returns
  snake_case keys and `state` is `open`/`closed` only — a merged PR reads `state=closed`, NOT `merged`,
  so "closed ⇒ not merged" is wrong; the merged fact is the boolean `.merged` (and `.merged_at`). And a
  camelCase jq key (`.mergedAt`, `.mergeCommit`) against the REST body returns `null` even on a merged
  PR — query the snake_case field (`.merged_at`, `.merge_commit_sha`) or use `gh pr view --json
  state,mergedAt` which does map them. Never conclude "mergedAt null ⇒ not merged" from a REST jq that
  asked for the camelCase spelling.
- **`--auto` on a green PR merges it immediately.** Arming is not a queue you can inspect afterwards:
  if the checks are already green and the branch is mergeable, `gh pr merge --auto` performs the merge
  at once. Read `mergeStateStatus` first if the PR was meant to stay reviewable, and report
  `auto=<enabledAt>` **or** `state=MERGED` — never claim "armed" for a PR that is already merged.
  **Read the arm back through ONE API spelling.** `gh pr merge --auto` exits 0 and arms nothing when the
  base is not the default branch, and the field is named differently per surface (`autoMergeRequest` in
  `gh pr view --json`, `auto_merge` in REST `gh api repos/<o>/<r>/pulls/<n>`) — jq'ing the other spelling
  returns null and reads as "not armed":

  ```bash
  gh api repos/<o>/<r>/pulls/<n> \
    --jq '{head:.head.sha[0:8],state:.mergeable_state,armed:(.auto_merge!=null),method:.auto_merge.merge_method,expected:.auto_merge.expected_head_sha}'
  ```

  `armed:true` + `state:blocked` is the honest **armed-but-pending** posture (CI is still running at
  that head); quote both rather than reporting a bare "armed". **The REST `auto_merge` object has NO
  `enabled_at` field** — `.auto_merge.enabled_at` is `null` on EVERY PR, so never read that null as "not
  armed" (`.auto_merge != null` in REST is the armed fact; the arm time lives only in GraphQL
  `autoMergeRequest { enabledAt }`). A lane quoting "it has no `enabled_at`, so it isn't armed" is
  quoting a phantom field.
- **A peer's ruling names a sha — verify it is the TIP, not your tip's parent.** A scope ruling measured
  at an amend's parent reads as "base is wrong / deletes the other lane's files" while the true tip is
  clean; the check is `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha` against
  `git rev-list --parents -n1 HEAD` (the second sha is the parent). Answer rulings by measuring the diff
  at the tip (`git diff --name-only origin/main <tip>`), and name the parent explicitly when a peer's
  numbers come from it — a disagreement that is one commit deep looks like a contradiction otherwise.
  **`git ls-remote <url> <arg>` matches ref NAMES, never commits** — passing a parent sha returns zero
  matches even though it is an ancestor on the branch, so an empty result is not evidence it never
  landed; prove ancestry with `gh api repos/<o>/<r>/compare/<parent>...<tip> --jq .ahead_by` (ahead_by 1,
  one intervening commit) or fetch the ref so `FETCH_HEAD` equals the branch sha.
  **A commit sha is "on the branch" only if it is an ANCESTOR of the origin ref — a commit that exists only in a local clone/worktree is not pushed.** `git log`/`git show` make a local-only commit look every bit as real as a pushed one; before citing a sha as "the fix on the branch", prove `git merge-base --is-ancestor <sha> refs/remotes/origin/<branch>` (and against `origin/main`) returns 0. The PR, the acceptance vehicle and CI all run the ORIGIN branch, so a citation of a local-only commit is a phantom claim a peer will refute. Drop it (name the origin tip instead) at the first signal; defending it costs credibility.
- **A peer lane's state report is a CLAIM about the wire — verify each claim separately before relaying or obeying it.** The recurring phantom shapes, often all in one message that sounds fully measured:
  (1) "current main is `<sha>`" while main sits at a later tip — read `gh api repos/<o>/<r>/branches/main --jq .commit.sha`; a lane reading its own stale clone-local refs quotes an older tip as current.
  (2) "I pushed `<sha>`" that never landed — `gh api repos/<o>/<r>/commits/<sha>` 404s, and even when it resolves, the PR's `.head.sha` must equal it before the push counts.
  (3) "PR `<n>` is open at `<sha>`" for a PR that was merged and whose branch is gone — read `gh pr view <n> --json state,mergedAt,headRefOid` (REST: `.merged` is the merged fact, `state` is only open/closed).
  Correct on the thread with the measured read and DM the lane once so it stops re-deriving the ghost; do not keep correcting the same stale premise round after round — deliver the measurement, then stop tracking it as live.
- **A sibling subagent can write into the worktree you own mid-edit — re-read the file and review the COMBINED diff before committing.** A "file was modified since you read it" warning is not always noise: another writer's refactor can land in the same file between your read and your patch. Confirm the writer has stopped (`sha256sum <file>` twice, a minute apart) and then read the WHOLE file / the full `git diff` rather than your own hunks — the composed content may be coherent (keep both changes) or may regress a sibling test (fix it before the commit). Never commit a diff noticeably larger than your change without knowing whose lines they are, and never revert the other writer's work because it was unexpected: it is often the real fix with your small correction on top.
- **A `@llgenie-planner` re-dispatch is a claim about time, not about the branch — re-measure before you obey OR refute it.**
  The planner's inbox acks lag your real state by rounds: it will "re-flag" a rebase you already pushed, cite a
  `head.sha` you superseded (an old head it still calls DIRTY), and order a rebase onto a `main` sha that main has
  already moved past — so obeying literally is a BACKWARD move. Before acting on any dispatch, re-read
  `gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha,base:.base.sha,mergeable,mergeable_state}'` and
  `gh api repos/<o>/<r>/git/refs/heads/main --jq .object.sha` fresh. If the PR already reads `mergeable=true`
  with `mergeable_state=blocked`, NO rebase is owed (owner rule #1015: rebase only on a real conflict) and
  forcing one destroys the in-progress CI run.  Do not ping-pong a fourth correction to a stale ack whose own
  text closes "quiet until …"; but DO send one terse measured correction when the planner is actively ordering a
  wrong action — silence lets it keep re-dispatching the same stale order to the whole fleet.
  **A peer's gate verdict can be red because it measured YOUR LOCAL WORKTREE tree, not the pushed head.** A
  planner/rebase lane reading your branch from a worktree extracts the LOCAL commit sha (e.g. your pre-fix
  commit) and runs `make <gate>` on that stale tree — so it reports "N reds at your live head" for a defect
  you already fixed and pushed. That sha is a local object, not a remote head: before accepting OR refuting
  the verdict, read the real head (`gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`) and re-run the gate at
  THAT tree. Answer with the measured exit at the true head ("LIVE=1 exit 0, 0 dead, at <head>") and state
  plainly that the peer's hash was a local/working-memory commit, not a remote head — the authoritative head
  is always what `gh pr view`/the pulls API reports, never a sha quoted in a DM or one you remember.
  **When the planner DM rejects as `queue_full` (no-resend), post the correction on the ISSUE/PR thread** —
  that is the record both the planner and the rebase lanes read, and re-DMing a full queue just wastes a
  turn. `queue_full` is not a delivery failure to retry; it is a signal to move the message to the thread.
- **A dispatch run pinned to an older sha stays valid when the workflow's real inputs are byte-identical.**
  An amend that only touches docs/census does not invalidate a `workflow_dispatch` confirm of an
  engine-build fix, because engine-build reads the Makefile, the workflow and the tests — not the docs.
  Decide by diffing the workflow's input files between the dispatch sha and the tip, never by comparing
  head labels; a pinned run is a snapshot of the tree at that sha and does not move when you push.
- **`git push` exiting 0 — or answering `Everything up-to-date` — is not proof the intended tree is on the
  remote.** Read it back: local `git rev-parse HEAD`, `git ls-remote origin <ref>`, and the PR's head
  (`gh api .../pulls/<n> --jq .head.sha`) must be the SAME sha before you report a push landed, and
  `mergeable` should be read back in the same call rather than inferred from the push's exit status.
- **A comment you just posted can look "phantom" only because you read a DEFAULT-SIZED page.** Verifying a
  comment by fetching `issues/<n>/comments` with the default page returns the OLDEST 30, so a successful
  just-now post is absent from `d[-1]` and reads as a phantom write that never landed — the exact false alarm
  that makes a lane re-post (and duplicate) a landed comment. Fetch with `?per_page=100` and check membership
  (`<new-id> in [c['id'] for c in comments]`), not just the last element; a comment reachable by
  `/issues/comments/<id>` is always also in the thread — if it is missing there, the cause is pagination, not
  a dead channel. Only a `404` on `/issues/comments/<id>` proves the write itself failed.
- **A PR's head lives in the repo named by `.head.repo`, which can be a FORK while the base is upstream.**
  When the head sha does not move after a push that clearly landed, read
  `gh api repos/<o>/<r>/pulls/<n> --jq .head.repo.full_name` before concluding "propagation lag": a
  branch pushed to the upstream repo carries no PR and no re-run, and the reviewer sees the fork's older
  commit. Push to the head repo (`git push <fork-url> HEAD:refs/heads/<branch>`), and lease against what
  that remote actually holds — `git ls-remote <fork-url> refs/heads/<branch>` — not a local remote-tracking
  ref, which is stale and gets the push rejected as `stale info`. Then read the PR head back from the API
  and quote it; a fork push and an upstream push carry the same commit but only one updates the PR.
  **Resolve the remote NAME, do not assume it is the owner's login.** A worktree's remotes are often named
  `fork` + `origin`, so `git push andyholst <branch>` answers `fatal: '<owner>' does not appear to be a git
  repository` while the URL is perfectly fine. Read `git remote -v` first (one call) and push to the
  resolved name; a push "failure" whose message names the OWNER, not a branch or a ref, is a remote-name
  error, never a permissions or lease problem.
- **A run `cancelled` at an old head after you pushed a newer head is NORMAL, not a red to explain.**
  `cancel-in-progress` (or head-moved supersession) concludes the previous head's run as `cancelled`; the
  cancelled run's jobs are not evidence about the current tree, and quoting them as "CI failed" is wrong.
  Judge CI only at the head you actually pushed: read the check-runs keyed by the FULL current sha and
  ignore old-head `cancelled` conclusions. The single healthy signal is "guard/holds/scope green at the new
  head, container jobs still in_progress" — a `BLOCKED` mergeStateStatus there means fresh CI pending, not
  a defect.
- **A long backoff with no output is indistinguishable from a hang.** Any wait loop over the
  network (a Hub 429, a retry ladder) must print what it is waiting for and for how long, on
  stderr. A silent multi-minute park gets reported to the user as a broken tool.
- **"That branch was never pushed" is a claim about ONE remote.** Ask each remote before you accept
  it: `git ls-remote origin <ref>` and `git ls-remote fork <ref>`. A branch pushed only to the fork
  looks absent from `origin` and gets reported as a single copy on one disk; re-pushing "for
  insurance" then starts publish-capable CI nobody wanted. Check both, quote the one that answered.
- **A test failure that reproduces on `main` is not your regression.** Before attributing it, run the
  same file on the untouched checkout. Some files are host-only by design and refuse a bare run —
  their own assert names the make target that runs them
  (`…assert BACKEND …, "run through make <target> BACKEND=…"`). Report it as pre-existing with both
  runs quoted, never as "my change broke the suite".
- **`git worktree add` takes PATH before the commit — `-b <branch> <path> <sha>`.** Passing the sha before
  the path (`… -b <branch> <sha> <path>`) parsed the path as a git ref and answered `fatal: invalid
  reference: <path>`. The reliable shape is `git worktree add -q -b <branch> <path> <full-sha>` (a short,
  unambiguous sha works; the `origin/main` short name stays forbidden), and `--detach <base-sha>` for a
  clean-base worktree.
- **Removing a worktree you were `cd`'d into leaves the persistent shell's cwd dangling.** The terminal
  session keeps its working directory between calls, so after `git worktree remove`/`rm -rf` of the
  directory you were in, every later command dies on arrival (exit 126 with
  `cd: <dir>: No such file or directory`) even when the command itself is fine — five identical
  failures that read as a broken tool. Recover with `cd /` (or an absolute `workdir`/`workdir=` per
  call), and prefer `execute_code` for the remaining probes: it starts from the session's declared
  working directory rather than the shell's last `cd`. Clean up in the same call you stop needing the
  directory — removing it from outside while the shell sits inside it is the setup for the loop.
- **Measure a clean-base gate red in a DETACHED worktree, not with `git stash`.** `git stash push -q
  include-untracked` (space-separated) fails to parse and leaves your tracked AND untracked changes in
  place, so a "clean" run measured after that false stash still contains your edits and misleads you
  into attributing a pre-existing failure to your change. `git worktree add --detach <base-sha>` gives the
  unambiguous clean base; run the gate there and compare the failure count before blaming your PR.
- **Run the failing file yourself before repeating a handed-over failure count.** "N failed at that
  head" is a claim about *their* checkout; reproducing it may show the failures are your own
  half-finished rename — fixable in the same commit — rather than the blocker you were told to
  report. Quote your own run, with the test names.
- **A commit message or PR body must not invent an issue number.** If the work has no issue, or the
  number arrived later, drop the reference and write the summary — a wrong `#NNN` sends reviewers to
  unrelated context and cannot be retracted once quoted.
- **Quote the heredoc delimiter when the text may contain backticks or `$`.** `git commit -F - <<EOF`
  (unquoted) runs command substitution inside the message: a `` `test_name` `` in the body executed as
  a shell command, "command not found", and the line was silently replaced — mangling the pushed
  message. Author commit messages and PR bodies with `<<'EOF'` (or `-F /tmp/file`), and read the
  message back with `git log --format='%B' -1` before pushing. When the body is assembled in **Python**
  (an `execute_code` call posting via the REST API), build it with `.replace()` on unique sentinel
  tokens, never `%`-formatting — a literal `%` in the prose collides with the format spec and raises — the
same collision bites the shell `printf` form. Sentinel-replace is the one shape that survives arbitrary prose.
- **A derived fixture is the one generator's output — regenerate it, never hand-edit it.** When a
  `check-*`/`test_*` gate over a committed derived table reds (a trend matrix, a quant catalog, a
  skill-gap report), run the generator (`make render-*`/`sync-*`) against the vendored data and take
  its output as the truth. A red that reproduces identically on a second run, on `main`, is data
  staleness — the vendored source moved — not flakiness and not the PR that merely runs the gate.
  Confirm the regenerated diff is confined to the generated file, and quote the row names from the
  failure (backend/params) to show they match what the diff touched.
  **Prove the regen is deterministic, not just present.** After writing the generator's output, re-run
  the SAME generator and confirm byte-identical output (hash the file before/after — a re-render that
  changes bytes will churn the file on every future run and reads as flakiness), then prove on-tree
  equivalence: `git hash-object <file>` on disk must equal
  `git rev-parse origin/main:<file>` after the merge (a rendered-but-not-committed file and a
  hand-edited one both answer a wrong blob). A regeneration that touches ONLY the committed data file
  and leaves the generator/code untouched carries no behaviour change, so it needs no
  `docs/changes.d` fragment — but confirm by the diff being confined to that one data file, not by
  assertion.
- **Never hand-type a full 40-char sha to key a watcher or API filter — `git rev-parse` it.** A
  display short sha (`git log --oneline`) widened to 40 hex characters by hand is wrong by
  construction: a fabricated `head_sha=`/`--json headSha` filter silently matches zero runs and the
  watcher parks forever, so the alarm is "CI never registered" when the real fault is a bad selector.
  Read the exact tip at the moment you key the watcher — `git -C <worktree> rev-parse origin/<branch>`
  — and pass that verbatim; re-derive it after every push because the head moves.
- **Never quote a workflow-RUN id you did not read back from the API.** Run ids are dense integers that
  look interchangeable; a guessed or carried-over id answers `404 Not Found`, so a report citing it as
  `SUCCESS` is a fabricated verdict about a run that does not exist. Enumerate the real ids at the head
  you mean, then quote from that listing:

  ```bash
  gh api "repos/<o>/<r>/actions/runs?head_sha=<full-sha>" \
    --jq '.workflow_runs[]|"\(.id) \(.name) \(.status) \(.conclusion)"'
  ```

  **After a squash merge the tip is the MERGE commit, not the PR head** — a post-merge "hf-live green"
  claim must list runs at the merge-commit sha (`.merge_commit_sha`) and quote one that actually ran
  there; the PR-head runs concluded before the merge and are not evidence about merged main. If the
  only fresh runs at the tip are still `in_progress`, say that (name the id and status), never promote a
  guessed id to `success`. If a wrong id already escaped in a report, correct it in the same thread with
  the real listing rather than silently moving on.
- **A `.PHONY` test must read the whole continuation block, not the first physical line.** The
  declaration continues across `\`-joined lines, so `MAKEFILE.split(".PHONY:",1)[1].split("\\",1)[0]`
  reads only line one and reds a target that was correctly added to a later continuation line — a
  false-negative that reads as "the target is not phony" and tempts you to edit the Makefile to match
  the test. Parse the block properly (every line starting with `.PHONY:` or a leading tab) or just
  assert the token is in the joined `.PHONY` text; fix the test, never the correct Makefile.
- **An openspec scenario that NAMES a test file must have that file actually assert the behaviour.**
  A spec delta can cite `tests/test_<y>.py` as the proof of a new step while that file predates the
  step and never mentions it — a spec that points at a nonexistent assertion is a gap only a reader
  catches, and it is a real defect owed in the same change, not a doc nit. After wiring a new workflow
  step or make target, grep the cited file for the assertion and add it: the step's ORDER (after the
  prior leg, truly last), the target's existence + `.PHONY`, and the wired seam (it pulls the
  as-published artifact rather than building).

## Owner-set holds are the owner's instrument

A `do-not-merge` placed by the owner (andyholst) is NOT this lane's to remove unilaterally, even when
another lane calls it vestigial or claims its reason has expired. Verify the claim by measuring before
either obeying it or removing the label:

1. **Who set the label, and does its named exit condition hold?** Read the issue events
   (`/{R}/issues/<n>/events?per_page=100`, filter `labeled`/`unlabeled`) for the actor + timestamp, and
   the remedy comment for the named condition. If the label's remedy ("removed when #N merges") has NOT
   landed, the reason has NOT expired — a bare holds-gate-green does not make it vestigial. Confirm the
   remedy itself: the master PR the label names must read `.merged=true`, not merely `state=closed`.
2. **The APPROVED that claims to supersede the hold may be a BOT, not the owner.** The `auto-merge`
   workflow approves every green PR that only lacked a required review, authoring the review as
   `asimov-agent` with a body that literally says "Approved by the repo's `auto-merge` job". That is an
   automated approval-on-green, NOT a human owner decision, and it does not lift an owner-set hold nor
   merge on its own while auto-merge is unarmed. Read the review's `user.login` AND its body before
   treating any APPROVED as "the owner approved" — a peer relaying "owner APPROVED" is often relaying
   this bot review. Only a review by the human owner account (or an explicit owner instruction) lifts
   the hold.
3. **A "this label blocks other PRs" claim is contradicted by measurement.** The `holds` gate audits the
   whole board, but `check-holds` reads "0 need attention" precisely because a held PR's do-not-merge
   NAMES its remedy — so a named-remedy hold does NOT red other PRs' holds legs. Verify the claimed
   victims directly: read each victim's `labels` (empty?), its `holds` conclusion (success?), and its
   red/in-progress check list. A peer asserting the hold reds others is answered by those three reads,
   not by the assertion.
4. **Removing an owner-set hold before its named remedy lands is the precondition-lift error.** The
   correct move is to keep it until the remedy lands, then remove it (naming the run/sha that proves
   the reason expired), or ask the owner explicitly. Never let a peer lane's premise — a green gate, or
   a bot approval dressed as an owner approval — substitute for the owner's instrument. Ask the owner
   in-chat when the premise is disputed; do not resolve it unilaterally either way.

## Closing a superseded / dead-weight PR — and which "issue" to close with it

When the owner says a PR should be closed (its premise is void — a capacity-only bump that is not the
real fix, a workaround superseded by another PR), closing is unambiguous: `gh pr close <n> --comment
...` citing the measured reason. Verify afterwards `state=closed` AND `.merged=false` (a close is not a
merge), and confirm any open fix PR that the dead one was gated behind still reads `mergeable:true`.

**"Close the PR and the issue" does NOT mean hunt for an adjacent open issue to close.** The dead PR
often carries "closes no issue" in its body — then there IS no tracking issue for it, and the only
open issue in the same area is usually the REAL-FIX TRACKER a still-open fix PR must deliver against.
Closing that tracker strands the acceptance vehicle (a merged fix with nothing left to prove against).
Before closing any issue, search by title AND body (`search/issues?q=repo:<o>/<r> \"<term>\"`), read
what the issue actually tracks, and check whether an open PR's boxes/tests depend on it. If the only
candidate is the real-fix tracker, do NOT close it — close the PR alone and say so; ask the owner to
name the issue when it is genuinely ambiguous rather than guessing. Closing a PR also voids its
`do-not-merge` label (the hold question is moot once the PR is closed, not "removed").

**Before you report an issue "eligible to close", read its state** — `gh api repos/<o>/<r>/issues/<n>
--jq '{state,closed_at,title}'`. A dependency-tracking issue is often closed by the owner at the very
moment its last condition's PR merges, so a lane announcing "now eligible" after that is describing
work already done; quote the actual `state`/`closed_at` instead of a recommendation the owner has
already executed.

## Versioning this skill in the repo (the `.hermes/skills` gate)

The llgenie repo keeps agent contracts in `.hermes/skills/<name>/SKILL.md`, and
`make check-agent-skills` refuses any skill there that no `hermes -z … -s <name>` leg
preloads (`skill-unused`). A HOST skill — an operator loop that needs a real GPU, so no CI
leg can load it — is admitted by NAME via the `HOST_SKILLS` frozenset in
`scripts/check_agent_skills.py`, exempt from the unused rule ONLY: it still owes frontmatter
(matching dir name + description) and `## Inputs` / `## Output` / `## Rules`.

- Admit by name, never by shape — adding another one must be a reviewed diff.
- Never invent a leg (a `hermes -z` recipe) just to satisfy the gate: a fake leg is the dead
  weight the rule exists to catch.
- Two files, one change set: the repo copy is what a reviewer reads, the profile copy is what
  loads on the host. Patch both, and run `make check-agent-skills` before committing.
- Do not fabricate a PR/issue number in the commit subject or body. If no issue exists, write
  the change summary without one.

## Versioning this lane's PROFILE (`agents/<profile>/`), which is a different gate

`.hermes/skills` (previous section) is not where this lane's own behaviour lives. The profile is
`agents/<profile>/SOUL.md` plus `agents/<profile>/skills/<name>/{SKILL.md,references/}`, mirroring
the live `~/.hermes/profiles/<profile>/`. Two checks cover it:

```bash
make sync-agent-profile PROFILE=<p> CHECK=1      # compare tool: live vs tree, refuses to write
HERMES_PROFILES_HOME=/nonexistent python3 scripts/check_agent_profiles.py   # tree structure only
```

- **`CHECK=1` is a COMPARE, and the live profile is usually the newer side.** "Reload the profile
  from the tree" is a plausible-sounding directive that would *truncate* behaviour (it once asked to
  replace an arm-auto-merge rule with the tree's older never-arm text). Run the compare and let it
  name the direction; when live is ahead, version live→tree in a PR instead of syncing tree→live.
- **The direction differs PER FILE inside one profile — never blanket-copy.** Measured: four files
  live-ahead while a fifth was tree-ahead, because a merged PR had advanced that file's tree copy
  (a product-scope change the live host never picked up). Copying every live file into the tree would
  have deleted merged content. Diff file by file, copy only the live-ahead ones, and state in the PR
  body why each untouched file was left alone.
- **The profile checker greps a LITERAL phrase, not the semantics.** Its manifest declares a regex per
  rule (e.g. `never\s+merge`), so a SOUL that says "do not hand-merge" and "never squash by hand"
  still reds. Satisfy it by *adding* the literal sentence where it belongs ("Never merge by hand")
  rather than reverting the newer directive: arming auto-merge and never performing the merge are
  compatible, because the `auto-merge` workflow executes the owner-gated squash, not this lane.
  Reword, never weaken the rule to pass a string match.
- **A SKILL.md that NAMES a `references/x.md` must ship that file.** Copying a newer SKILL.md alone
  reds the checker on the named-but-missing reference; copy the reference in the same commit.
- Check it is really the tree gate you cleared: `check_agent_profiles.py` prints
  "tree checks only, LIVE RULEBOOKS NOT COMPARED" — green there does not mean live and tree agree.

**Fragment filenames embed the issue number, so file the issue FIRST.** `docs/changes.d/<date>-<slug>-<issue>.md`,
its `agent-wiki/` sibling and the commit subject all carry `#NNN`. Guessing the number costs a `sed`, two
`git mv`s, a `make changes-index` regen and a `git commit --amend` plus a PR-body edit to repair — create
the issue, then name the files from its real number. And a fragment/number mismatch reds the
change→note gate in a way that reads like an unrelated docs error.

**A mid-flight pivot invalidates the change's own THREE doc records — fix all of them, not one.** When the
mechanism of a fix changes after the change-record was written (source-build → restore-prebuilt, a knob that
turned out dead, a superseded approach), the record that narrates the OLD mechanism is stale-adjacent and
misleads the next reader. Three copies must agree, and a grep for the old mechanism row catches all three:
`agent-wiki/<date>-<slug>-<issue>.md` (the narrative page — add a "Pivot during implementation" section
naming the measured result that forced the new direction), its one-line row in `CHANGES.md`, and the
byte-matching copy in `docs/changes.d/<date>-<slug>-<issue>.md`. Re-run `make openspec-validate
NAME=<change>` after the edit; the change must still read `is valid`.

**When the pivot's docs are discovered while a proof run is live at the head, STAGE them and hold HEAD.**
Committing (or amending) the doc fix moves the branch head, which supersedes the in-flight proof's sha and
reproduces the "proof pinned at a superseded head" defect. Correct sequence: `git add` the doc edits, keep
`HEAD` at the proofed sha (verify with `git rev-parse --short HEAD`), and commit+push the staged docs only
after the proof verdict lands — so the merged PR's docs match the head that was actually proven. A docs
change is not a reason to cancel or supersede a running matrix.

**Gate set for a profile-versioning PR** (run all, quote each): the profile checker above, `make check-docs`
(census pointer must be an ancestor of HEAD), `make changes-index`, `make lint`, and the hermetic
openspec/ci-images pytest.

**`check-docs` reads the COMMITTED `base..HEAD` diff, not the working tree.** A behavioural change under
`agents/<profile>/` owes an `agent-wiki/<stem>.md` note + its `docs/changes.d/<stem>.md` row, and the gate
flags it as red the instant the changed file is committed — but a note trio you wrote and left UNTRACKED is
invisible to the gate, so `make check-docs` still reds `adds no agent-wiki/<stem>.md note` even though the
file is sitting on disk. Stage and commit (amend into the same commit) the agent-wiki note, the changes.d
row and the rendered `CHANGES.md` together, THEN re-run `make check-docs` — a green measured before the
commit is a measurement of a tree the gate never read. `CHANGES.md` itself is rendered from the fragments
(`python3 scripts/changes_index.py write`, alias `make changes-index`); never hand-edit it, or a
regenerate silently rewrites your edit away.



**Never put a run id, flow id, sha, or timestamp into a report/comment unless it was READ BACK from the API in the SAME turn as the write.** A plausible-looking id — e.g. hf-live run "41558411804 / success" — that was invented, not verified, is fabricated evidence and is incident-worthy on a close proof. Posting an unverified run id on an issue (close-condition evidence) caused a public correction and a board-credibility hit. Rule: every metric/run/stream id you cite must come from a live `gh api` read (or the tool output of the current call), never from memory or pattern-matching. When a run is still in_progress, say "in_progress / conclusion unset" — never invent a conclusion. If you cannot reach the API, say so and report nothing, rather than fabricate.


**Do not call a run "stalled" from its updatedAt alone.** A frozen run-level updatedAt is NOT a stall signal: GitHub does not bump the run's updatedAt mid-step, so a long "in_progress" with recent job-step activity is normal for long single steps (e.g. the @pytest.mark.network suite). To judge stall, read the RUN's associated JOB steps (`gh api repos/.../actions/runs/<id>/jobs`) and check whether the current step's started_at is recent and the job's updated state has real step progress; only a step whose started_at stalled with NO step completing for well past its normal duration is a candidate. Announcing a "stalled-run finding" on an issue from updatedAt alone, then having it retracted by the verdict owner, is an over-read that undermines the same on-record discipline as a fabricated id.

**A 215-byte BlobNotFound XML on the job logs endpoint is "log not finalized", not a suspension, on ANY young in_progress job** (reaper calibration, #1679, measured 2026-11-03): GitHub serves logs only AFTER the job completes, so a fresh running job's blob 404 is the NORMAL pre-completion state — a discriminator keyed on in_progress+BlobNotFound false-positives every healthy matrix cell. A real suspension is a STALL past a floor: in_progress AND two consecutive reads show unchanged updated_at AND no progress events AND no arriving conclusion. Floor per slice = 2× that matrix slice's own completed-run median (measured: linux/unit completes 9.0–14.1 min, median ~12.5 → floor ~25 min; install ≤4.1), never a fixed 10-min constant — a healthy unit is in_progress at 10 min routinely (proof: #1680 job 125756825660, 11.2 min success, zero-byte blob the whole time). Post run id + both timestamps + PR before any reaper cancel.

## Quant-catalog LIVE=1 seam (#1712/#1720)

The hermetic `make check-quant-catalog --snapshot` gate can NEVER catch dead links: its
`_snapshot_probe` returns PROBE_OK for link liveness by design (issue #1178) — dead-vs-reachable is the
LIVE seam's job (`make check-quant-catalog LIVE=1`). A drift like laguna chat_template.jinja 404/410
passes --snapshot yet reds LIVE=1. To get the authoritative verdict run the actual
`make check-quant-catalog LIVE=1` at the head (network, ~5 min) AND repeat 3–5x — a stable dead verdict
= real drift (fix with live `make sync-quant-catalog` drop-dead), not a flake. A raw urllib probe can
read 401 where the generator reads dead; trust the generator's own `_probe_status`, not a hand-rolled
request. ci-hf-live.yml runs ONLY on main (never a PR head), so a PR-head LIVE verdict cannot get a GH
run id — the honest evidence is the local seam run; report the GH run id after it merges to main. When a
fix(engines)/data PR's refresh is direction-right but incomplete, extend the PR (drop the surviving dead
rows) rather than file separately.

## Driving a CI to its conclusion — the verdict IS the task

When the acceptance criterion for the work is a CI verdict ("is this PR green at head X"), reporting
`guard/holds success, containers in_progress` is NOT done — it is in-flight, and a guard/peer will
rightly bounce it. Drive the run to `completed` and quote the conclusion. Two mechanics:

- **Dedupe the latest conclusion per check name in ONE read** — check-runs accumulates every re-run, so
  naively listing them shows stale `failure`s beside a fresh `success`. Group by name and take the last:

  ```bash
  gh api "repos/<o>/<r>/commits/<full-sha>/check-runs" \
    --jq '.check_runs|map({n:.name,c:.conclusion})|group_by(.n)|map({n:.[0].n,c:map(.c)[-1]})|map("\(.n): \(.c//"-")")|.[]'
  ```

  A `-` conclusion is genuinely not-yet-set (in_progress), never a pass. Cross-check the discrete runs
  with `gh api "repos/<o>/<r>/actions/runs?head_sha=<full-sha>" --jq '.workflow_runs[]|"\(.id) \(.status)/\(.conclusion//"-")"'`
  and quote a real id — never a remembered one.
- **A ~10-min matrix cannot be driven to conclusion in ONE foreground `terminal` call** (the foreground
  cap is ~420 s; a `for … sleep 30` loop over a 10-minute run dies on the cap and reports a *tool*
  timeout, not the run's verdict). Poll in `execute_code` with `time.sleep(60)` between `gh api` reads and
  stop on `status==completed` OR `in_progress==0` — a poll loop that finishes inside the cell window
  returns the real conclusion; keep it to ~10 iterations. Fall back to a `background=true, notify=true`
  watcher only when the run is expected to outlast the cell window, then read the watcher's final output
  rather than a sleep-loop inside it.
- **A watcher's completion matcher must COMPARE the phase string, never `case "$st" in completed|*)`.**
  The status is read as `"<status>|<conclusion>"` (e.g. `in_progress|pending`); a `case` pattern
  `completed|*` has `*` as a CATCH-ALL alternation that matches `in_progress|pending` too, so the loop
  takes the "done" branch on its FIRST read and prints `DONE` for a job still running — a fabricated
  completion. Split the phase (`ph="${st%%|*}"`) and test `[ "$ph" = "completed" ]`; only then is the
  conclusion authoritative.

## Moving-main base-drift (check-pr-base ~#845, check-pr-sync-line, stale-head gates)

The CI guard's `make check-pr-base` (scripts/check_pr_base.py) fetches origin/main LIVE and requires
HEAD's merge-base to be exactly origin/main. On a busy fleet, main advances between your rebase and the
CI read, so a freshly rebased head can red check-pr-base a 2nd/3rd time for NO content reason — base
drift, not a defect. Rebuild: rebase onto the live origin/main tip; `git merge-base HEAD origin/main`
must equal `git rev-parse origin/main`; run `check_pr_base.py check --base origin/main --rev HEAD`
locally (OK = merge-base==base); re-verify seams; push with lease. Each post-rebase main merge
invalidates until rebuilt — expect to redo it once or twice queued behind a busy queue. Never weaken
the gate or blame content. Also re-run `changes_index.py check` after the rebase (new main rows land).

**A `check-pr-sync-line` red that names a directory your diff never touched is the SAME base-drift, not
a missing SYNC line.** The sync-line gate diffs against LIVE `origin/main`, not the PR's declared base. When
main advances past your base by landing another PR that edited `agents/<profile>/`, that foreign change
enters the gate's `origin/main...HEAD` diff-scope and the gate misattributes it to your PR — demanding a
`SYNC:` line for a path that is not in your real diff. Prove it before you obey: diff your actual range
(`git diff --name-only <your-base>...HEAD`) and the gate's range
(`gh pr diff <n> --name-only` or `git diff --name-only origin/main...HEAD`); if the named dir is absent
from YOUR range and present only in the live-main delta
(`git log --oneline <your-base>..origin/main` names the offending PR), it is a phantom. The fix is the
SAME rebase onto live `origin/main` that clears `check-pr-base` — it re-bases the diff-scope so the
foreign change is already in the base and no longer diffs as yours. **Never add the demanded SYNC line to
silence it** — that conserves a phantom and pollutes the PR body with a route it does not own.

**Read a gate's conclusion at the CURRENT head, not at the head the dispatch or a stale log quoted.** A
`check-pr-authors`/`guard` red often belongs to a PRIOR head that a later re-author already fixed: before
you do any re-author the dispatch asks for, group the check-runs at the live head
(`gh api 'repos/<o>/<r>/commits/<full-sha>/check-runs?per_page=100' --jq '.check_runs[]|select(.name=="guard")|[.status,(.conclusion//"-")]|@tsv'`)
— three `success` lines mean the author gate is already green and the re-author is moot; the red was the
superseded head. Confirm the commit author at the live head (`git log -1 --format='%an <%ae>' <full-sha>`) is
an allowlisted identity before concluding. A dispatch that orders a re-author is a claim about time; the
current-head guard is the measurement that decides whether any action is owed.
