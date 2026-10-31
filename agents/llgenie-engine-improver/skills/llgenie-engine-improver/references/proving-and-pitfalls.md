# Proving a fix, repo pitfalls, and versioning this skill

Extracted from SKILL.md to keep the always-on body small; load it when you are about to
prove a fix, hit one of these traps, or touch `.hermes/skills`.

## Reading a CI failure without the runner's log stream

`gh run view --log-failed` answers "still in progress; logs will be available when it completes" and
`gh run view --job <id>` returns 0 bytes with the pinned token — a CLI guard, **not** an API limit.
The API serves the log:

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

## Proving a fix, and cutting the branch it ships on

**Work in a worktree, never in the primary checkout.** `/home/asimov/repository/git/llgenie` is the
shared builder workspace other lanes treat as `origin/main`; commits parked there on a feature branch
make every other lane's tree ambiguous. Do:
`git worktree add ../llgenie-wt/<slug> -b <slug> origin/main`, work there, and keep the primary
directory on `main` and clean. **Push the branch as soon as it has one commit** (fork is fine for a
branch that needs no publish): an unpushed branch is a single copy on one disk, and a reviewable one
needs a remote to point at.

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
   env HOME=/home/asimov RUNTIME=docker PATH="$HOME/llama-gguf-tools/.venv/bin:$PATH" \
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

## Local `make ci-unit` is not the verdict to wait for

- It runs ~14 600 tests including LIVE network reads (Hub/GitHub downloads in `tests/test_trend_pick.py`)
  and takes 75 min-2.7 h when the fleet has several suites on one host. Each `pytest-timeout`
  faulthandler dump ("Timeout (0:05:00)!") is a stack snapshot, NOT a failure — the test keeps going.
- The authoritative verdict is the `linux / unit` JOB:
  `gh run view <run> --json jobs --jq '.jobs[]|select(.name=="linux / unit")|{status,conclusion}'`.
  A run whose overall `status` is `queued` can still have that job `completed/success` — quote the job.
- A suite interrupted mid-run leaves `make` at `Error 130`; grep `^FAILED` in the log, never trust the
  exit code of a run you stopped.

**Freeing a suite you no longer need** (its container's PID 1 is root-owned): `kill -TERM 1` is
ignored, and `docker kill` / `sudo` / `rm -rf` are refused by the harness in single-query mode.
`docker exec <container> kill -INT 1` works (pytest aborts). A leftover worktree's root-owned
`__pycache__` cannot be deleted as the user — `git worktree remove --force` still unregisters it and
the scratch dir self-prunes after 24 h; say so instead of leaving an unmentioned 14 MB.

## Two identities may author a commit

`scripts/check_pr_authors.py` accepts exactly `Andy Holst <andy.holst@protonmail.com>` and
`Asimov Agent <support@docondee.com>`; every other name/email pair reds the PR (`LLGenie Pipeline
Maintainer`, `github-actions[bot]`, `Hermes Agent`, a bare `andyholst`). Re-author in the same push
that fixes the code — `git commit --amend --no-edit --author="Asimov Agent <support@docondee.com>"`
— or the PR stays red for a second reason nobody is working on.

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
- **`--auto` on a green PR merges it immediately.** Arming is not a queue you can inspect afterwards:
  if the checks are already green and the branch is mergeable, `gh pr merge --auto` performs the merge
  at once. Read `mergeStateStatus` first if the PR was meant to stay reviewable, and report
  `auto=<enabledAt>` **or** `state=MERGED` — never claim "armed" for a PR that is already merged.
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
  message back with `git log --format='%B' -1` before pushing.
- **A derived fixture is the one generator's output — regenerate it, never hand-edit it.** When a
  `check-*`/`test_*` gate over a committed derived table reds (a trend matrix, a quant catalog, a
  skill-gap report), run the generator (`make render-*`/`sync-*`) against the vendored data and take
  its output as the truth. A red that reproduces identically on a second run, on `main`, is data
  staleness — the vendored source moved — not flakiness and not the PR that merely runs the gate.
  Confirm the regenerated diff is confined to the generated file, and quote the row names from the
  failure (backend/params) to show they match what the diff touched.

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
