# Auditing and repairing llgenie's GitHub Actions bots

The scheduled bot workflows (issue-bot, fix-bot, issue-refiner, rebase-bot, engine-bump,
engine-bump-rebase, registry-sync, queued-alarm, run-failure-reactor, code-review-bot,
search-smoke, publish-agent-image) are verified by reading their **runs**, never by reading
their YAML and concluding "looks right". A run that is green can be a no-op, and a run that
is red is usually one broken assumption repeated on every schedule.

## Audit procedure (in this order)

1. Sync the checkout first: `git fetch origin --prune && git pull --ff-only origin main`.
2. Every workflow, its last runs:
   ```bash
   for f in .github/workflows/*.yml; do n=$(basename "$f"); echo "=== $n"; \
     gh run list --repo asimov-agent/llgenie --workflow "$n" --limit 3 \
       --json databaseId,status,conclusion,event,createdAt \
       --jq '.[]|"\(.databaseId) \(.createdAt) \(.event) \(.status)/\(.conclusion)"' ; done
   ```
   `workflow_call` files (pipeline.yml, published.yml) have no runs of their own — their jobs
   appear inside the caller's run.
3. For each red run: `gh run view <id> --log-failed | grep -E '##\[error\]|Error|Traceback|KeyError|403'`.
   `--log` is unavailable until the run completes; `--log-failed` on an in-progress run prints
   nothing, which is not evidence of success.
4. For each green run, prove it **did** something. Grep its own markers:
   `gh run view <id> --log | grep -E '\[<bot>\]|action=|skip #|no findings|no job|nothing'`.
   Three legitimate green-but-no-op shapes, each a separate defect if unintended:
   * the picker finds nothing to pick (no issue carries the gate label);
   * its daily cap reads 0 because it counts an author the bot never uses;
   * every candidate is skipped (e.g. every PR head lives on a fork).
5. Reproduce a suspected code bug with the repo's own entry point before editing, and prove the
   fix with a **negative control**: the same command against the unmodified tree (a second
   checkout, `git show HEAD:<file>`, or a temp dir holding the old files) must still fail the way
   the issue describes. A test that only passes on the new tree proves nothing.

## The credential split (the most common bot failure)

A bot step writes with the credential that can make the write. The job's `permissions:` block
already declares what is allowed; the token must match it.

| the step does | token | why |
|---|---|---|
| comments on / labels an **issue** | `${{ github.token }}` | job declares `issues: write`; an owner PAT scoped for pushing carries no Issues write and fails `GraphQL: Resource not accessible by personal access token (addComment)` |
| **dispatches** a workflow (`gh workflow run`) | `${{ github.token }}` | job declares `actions: write`; a push-scoped PAT fails `403 … /dispatches` |
| **pushes** a branch / opens a PR | `secrets.BUMP_TOKEN` | a `github.token` push does not re-trigger CI |

Pitfalls that cost time:

* A workflow can declare the right `permissions:` and still hand the step the PAT — the
  declaration is not the write. Read the step's `env.GH_TOKEN`, not the job header.
* `git push` uses the credential `actions/checkout` persisted in the remote URL, **not**
  `GH_TOKEN` (which only authenticates `gh`). A pushing job is therefore safe when its checkout
  was given the PAT, even if the step env says `github.token`.
* After fixing a step, grep the test tree for the old token literal: a test that pins
  `GH_TOKEN == '${{ secrets.BUMP_TOKEN }}'` for that step reds the suite, and the update must
  carry the new rule (token **and** the declared permission), not just the new string.
* Verify with a real dispatch from the branch before opening the PR:
  `gh workflow run <bot>.yml --repo asimov-agent/llgenie --ref <branch>`, then read the run and
  the issue it touched (claim comment, review comment, report). "The step no longer 403s" is
  weaker than "the run succeeded and the three posts are on the issue".

## Pinned model / version snapshots

A pin asserted by **substring** silently accepts any newer value: an assert on
`"deepseek/deepseek-v4.1-flash"` passes for `…-1017` and for `…-1102` alike, so the bots ran a
superseded snapshot while every gate stayed green. The durable shape:

* declare the pin once in a module (`MODEL_ID`, budgets), compare every file that carries it
  (Dockerfile `ARG` default, install script default) against that one value, and fail naming
  **the file and the value it read**;
* assert the exact id in tests and add the case where a *newer* id is the drift — that is the
  case a prefix assert cannot catch;
* when two ids both answer 200, only a catalogue read tells them apart (`/v1/models`
  `canonical_slug`), so put that comparison in the issue as the evidence;
* assert the whole alias at **build** time (model, provider, key_env, max_tokens,
  context_window): a half-written config then fails the image build, not a 120-minute bot run.

## GHCR / agent-image publishing

* Publish with the credential the working sibling path uses: `secrets.GITHUB_TOKEN` +
  `packages: write`, logged in as `github.actor` — exactly as `ci.yml`'s `ci-images` job
  publishes the test image. An owner PAT without `write:packages` fails the job's own push-check
  (`403 DENIED … does not match expected scopes`); the pre-flight is right, the credential was not.
* The tag is a hash of the image's inputs: `python3 scripts/ci_images.py ref agent`. Changing the
  Dockerfile **or** any COPY'd install script moves it; adding a workflow or a README does not.
  So a `workflow_dispatch` of the publish workflow **from a feature branch** publishes the same
  tag `main` will compute — no merge needed to exercise the publish path.
* Verify what was published by pulling the tag and reading the config inside it
  (`docker run --rm <tag> bash -lc 'hermes config get model.aliases.<a>.model'`), never by
  trusting the build log.
* `gh api /user/packages/container/<name>/versions` lists the **authenticated user's** packages.
  When the repo owner is a user account (not an org), that is `/users/<owner>/packages/...`;
  `/user/...` answers `Package not found` and looks exactly like "never published".

## Working a change in this repo (traps)

* `make openspec-new NAME=<kebab>` runs its container as root, so the new change dir (and its
  `.openspec.yaml`) is owned by root and writing `proposal.md` into it fails
  `Permission denied: …/.hermes-tmp.xxxx`. Chown it through a container — that needs no privilege
  at all:
  ```bash
  docker run --rm -v "$PWD/openspec/changes/<name>:/c" alpine:3 \
    chown -R "$(id -u):$(id -g)" /c
  ls -la openspec/changes/<name>     # confirm the owner before writing
  ```
  `sudo chown -R $USER:$USER …` is the same fix but needs a password on a host without
  passwordless sudo (`sudo: no password was provided`) and a TTY when backgrounded; the docker
  path is the one that works from anywhere. The `.openspec.yaml` the CLI wrote stays as it is —
  fix ownership, never re-create the change dir by hand.
* Tick the final verification checkbox only **after** the gate passes. An unticked box reds
  `linux / openspec` (`[openspec-tasks] FAIL <change>: unchecked task checkbox(es)`), so a red
  openspec job on a fresh PR is usually that, not a real failure.
* Run unit tests through `make test-unit` even from a worktree: it mounts the parent repo, so
  tests that shell out to `git show HEAD:data/...` work. A raw `docker run -v $PWD:/repo` makes
  them fail with `fatal: not a git repository: …/.git/worktrees/<name>` — an artifact of the
  mount, not a broken test.
* Fast loop before the gate: run ONE file in the test image, mounting the parent clone at its own
  absolute path exactly as `make test-unit`/`lint` do (without that second mount, a worktree whose
  `.git` is a FILE makes `git`-reading tests die with `not a git repository`):
  ```bash
  p=$(git rev-parse --path-format=absolute --git-common-dir); p=$(dirname "$p")
  docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root -v "$p":"$p":rw \
    llgenie/test:latest python -m pytest tests/test_<x>.py -q -p no:cacheprovider
  ```
* The suite is ~14 minutes: run it as a background job with notify, and watch progress with
  `docker logs --tail 3 <container>` (a `| tail` in the recipe hides everything until exit). Do
  not start a second run while one is going; two containers cost the same wall clock twice.
* **A green `make test-unit` log can still contain `Timeout (0:05:00)!` and a thread dump.**
  pytest's watchdog fires inside a test that then finishes anyway, prints the dump between
  progress dots, and the suite reports `passed`. Read the log for `Timeout (` before believing a
  run: a 19-minute suite that normally takes 13 is that stall (a real model download spun up by a
  "hermetic" test), not a slow host. Verification is "green AND no watchdog dump", never just the
  final line.
* Remotes in this checkout are `origin` = `asimov-agent/llgenie` (upstream) and `fork` =
  `andyholst/llgenie`. Run `git remote -v` before pushing: `git push -u origin <branch>` would
  target the upstream, and the fork head is what the PR needs
  (`gh pr create --repo asimov-agent/llgenie --head andyholst:<branch>`). AGENTS.md's "push to
  origin (the fork)" predates this worktree's remote naming.
* `make check-quant-catalog` reds on a host without an authorized `HF_TOKEN` (the generator then
  cannot see gated Hub repos and its output drifts). Check that target's line in a CI `unit` log
  before calling it a code defect.
* A gated Hub file answers `401`, not `404`: a link probe must classify `ok` (200/206) /
  `gated` (401/403) / `dead` (else) and fail only on dead — one gated model otherwise blocks the
  whole registry refresh.

## Issue → PR discipline for these fixes

One defect, one issue, one branch, one PR. A fix that is only *partly* implementable (the
upstream data is lossy, the store must be fixed upstream first) does **not** close the issue —
the PR names what remains as a linked work item. Report upstream rather than widening a guard:
`llgenie never patches upstream data to make a sync pass`.
