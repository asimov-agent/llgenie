# Repo work in llgenie: worktree → OpenSpec → gates → PR

The procedure for one change in `asimov-agent/llgenie`, in the order that survives CI.
AGENTS.md carries the policy; this file carries the mechanics and the traps that cost a run.

## Remotes are named the opposite way round from AGENTS.md's prose

```
fork   https://github.com/andyholst/llgenie.git      # the FORK (push here)
origin https://github.com/asimov-agent/llgenie.git   # the UPSTREAM (base of the PR)
```

AGENTS.md says "push the branch to `origin` (the fork)" — in this checkout `origin` is the **upstream**.
Every PR is therefore:

```bash
git push -u fork fix/<kebab>
gh pr create --repo asimov-agent/llgenie --base main \
    --head andyholst:fix/<kebab> --title "<typed>(scope): summary (#N)" --body-file /tmp/pr.md
```

Check `git remote -v` once per worktree instead of trusting either name.

## Worktree, then the OpenSpec change, then code

```bash
git fetch origin main
git worktree add -b fix/<kebab> ../llgenie-wt/<kebab> origin/main
cd ../llgenie-wt/<kebab>
make openspec-new NAME=<kebab>
```

`make openspec-new` runs the OpenSpec CLI **in a container as root**, so the change directory comes back
root-owned and the first write into it fails with `Permission denied`. Fix the ownership with the engine
already present (no sudo needed):

```bash
docker run --rm -v "$PWD/openspec/changes/<kebab>:/c" alpine:3 chown -R "$(id -u):$(id -g)" /c
```

## The two gates that are not obvious

`ci-openspec` runs **both** `openspec-validate NAME=ci-pipeline` and `openspec-tasks-check`. The second
fails any active change whose `tasks.md` still has a `- [ ]` box, so the PR is red for bookkeeping, not
code. Tick each task as it is verified and check locally before pushing:

```bash
python3 scripts/check_openspec_tasks.py        # per-change OK/FAIL, exit 1 on any unticked box
```

Passing an argument makes it look up a change **named** that argument, so `check_openspec_tasks.py check`
prints the misleading `FAIL check: no active tasks.md (archived/missing)`. Run it bare.

`pytest.ini` sets only `faulthandler_timeout = 300`, which **dumps stacks and keeps going**: a run can
stall five minutes and still report `N passed`. A dump is not a verdict. If a green suite got slower or
printed `Timeout (0:05:00)!`, the cause is a test that leaves the machine (Hub link crawls, real GGUF
downloads); move it to a target that owns network (`make test-hub-live` is the shape), de-selected from the
hermetic gate by exact node id in `tests/fixtures/unit-suite.json` (`deselect`), never by `-k`.

## Run unit suites one at a time

`make test-unit` takes ~11-17 minutes. Two concurrent runs fetch the same Hub links and the link tests go
red on `HTTP Error 429: Too Many Requests` while the tree is fine. Chain branches in one shell
(`run a; run b; run c`) rather than fanning out, and re-run a lone 429 later instead of chasing it.

## When your change moves a single source of truth, grep the suite for the literal

Changing a Makefile variable, a recipe line or a function signature breaks tests that pinned the **old
string**, and they fail on a later shard, not where you looked:

```bash
grep -rn "\$(nous-alias)\|--wants\|def _gh\|Reply with exactly" tests/ Makefile scripts/
```

Update those assertions to the new single source (e.g. read the alias from one variable). Do not add a
second test beside the stale one, and do not weaken the assertion into a tautology.

## Rebase the moment main moves

A branch cut before someone else's merge comes back `CONFLICTING`, and GitHub schedules **no workflow runs
at all** for it (`gh pr checks <n>` → `no checks reported`, `statusCheckRollup` empty). Resolve the
conflict yourself, then:

```bash
git fetch origin main && git rebase origin/main
git push --force-with-lease fork fix/<kebab>     # allowed on your own PR branch only
```

Re-run `check-wiring`, `check-docs` and `check_openspec_tasks` after the rebase: a conflict resolved in the
Makefile `.PHONY:` block or the wiring fixture is the usual casualty.

## Prove it with the real thing, not with prose

A bot-facing claim (a mount, a token, an ignore rule, a CLI refusal) is cheap to demonstrate — and the
demonstration belongs in the PR body:

- container mounts: `docker run --rm -v "$PWD":/repo -w /repo alpine:3 sh -c 'echo x > ../outside/f'` and
  show the host never sees it, while a write into `/repo` does;
- per-call credentials: run the real `gh` through the code path with a bogus value and show the `401`;
- ignore rules: `git check-ignore -v <name>`, plus a throwaway repo showing the file is not a pending change;
- a refusal: run the command with the missing/thin input and paste its exit code.
