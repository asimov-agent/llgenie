# llgenie: bot credentials, real remotes, and the gotchas that cost time

Measured on `main@e622858` (2026-10-20) while auditing every Actions bot.

## Remotes are the opposite of AGENTS.md

In `/home/asimov/repository/git/llgenie`:

| remote | repo | role |
|---|---|---|
| `origin` | `asimov-agent/llgenie` | **upstream**, the PR base |
| `fork` | `andyholst/llgenie` | the fork, the PR head |

AGENTS.md says "push to origin (the fork)" — for THIS checkout `origin` is upstream. Correct shape:

```bash
git push fork <branch>            # and also: git push origin <branch>
gh pr create --repo asimov-agent/llgenie --base main --head andyholst:<branch>
```

Pushing the branch to upstream too makes `workflow_dispatch --ref <branch>` possible (the ref must exist
in the repo that owns the workflow).

## Which credential makes which bot write

`secrets.BUMP_TOKEN` is a push PAT. It carries **no** Issues write, **no** Actions write, **no**
`write:packages` — each was measured as a hard 403:

- `gh issue comment` → `GraphQL: Resource not accessible by personal access token (addComment)`
- `gh workflow run` → `HTTP 403 … /dispatches`
- GHCR push → `DENIED permission_denied: The token provided does not match expected scopes`

Use `${{ github.token }}` for issue/PR comments, labels and `gh workflow run`, with the job declaring
`issues: write` / `actions: write`. Keep `BUMP_TOKEN` for `git push` (a `github.token` push does not
re-trigger CI), and note `git push` authenticates with the token `actions/checkout` persisted, not with
`GH_TOKEN`. Lock the split in a test that reads each workflow's steps — `tests/test_bot_write_tokens.py`
is the reference implementation.

## openspec-new in a worktree

`make openspec-new NAME=<x>` runs the container as **root**, so `openspec/changes/<x>` is root-owned and
writing into it fails with `Permission denied`. Fix in the same foreground call:

```bash
make openspec-new NAME=<x> && sudo chown -R asimov:asimov openspec/changes/<x>
```

`sudo` fails in a background/non-TTY shell (`a terminal is required to read the password`) — never put the
chown in a backgrounded chain.

An unticked `- [ ]` in `openspec/changes/<x>/tasks.md` reds the `ci-openspec` job
(`openspec-tasks-check`). Tick the verification task only after the gates ran, then push.

## Local vs CI disagreements that are NOT defects

- `make check-quant-catalog` reds locally without an authorized `HF_TOKEN`: the generator cannot list the
  gated repos (`TensorFold/*`), so its output drifts from the committed table. In CI, where the token is
  set, the same target passes (its job log has no `make: ***`).
- `engine-image-none-none` / `test-published-none-none` running green on main is **correct**: the matrix is
  `make -s list-engine-images CI=1 JSON=1 CHANGED=<parent>`, and a merge that touched no engine build
  input (params, Dockerfile, skill) returns the `none` sentinel by design (#153).

## Reading a bot's real work, not just its colour

Job-level `success` hides a no-op. Grep the run log for the tool's own decision markers:

```bash
gh run view <id> --log | grep -E '\[(sweep|rebase-bot|code-review|queued-alarm|issue-refiner)\]'
gh run view <id> --log-failed        # the failing step — empty until the run COMPLETES
```

`make issue-bot-dispatch REPO=asimov-agent/llgenie FORCE_ISSUE=<n> DRY=1` proves the picker end to end
(picks, prints `agent/issue-<n>-<slug>` and `daily count N/3`) without writing anything.

## GHCR package is user-owned

`asimov-agent` is a **user**, not an org. `gh api /user/packages/...` 404s; list versions with:

```bash
gh api "/users/asimov-agent/packages/container/llgenie%2Fagent/versions" \
  --jq '.[]|"\(.metadata.container.tags|join(",")) \(.created_at)"'
```

`publish-agent-image.yml` publishes with `secrets.GITHUB_TOKEN` + `packages: write` (the same credential
`ci.yml::ci-images` uses). Verify a published image by *pulling* it and reading the alias:

```bash
docker pull -q ghcr.io/asimov-agent/llgenie/agent:<hash>
docker run --rm <ref> bash -lc 'hermes config get model.aliases.nous-deepseek.model'
```

## Model pin

`scripts/agent_model_pin.py` (with `make check-agent-model`, run by `ci-unit`) is the single declaration of
the bots' model (`deepseek/deepseek-v4.1-flash-1017`), compared against the agent Dockerfile's
`ARG HERMES_MODEL_ID` and the install script's `MODEL_ID`. The unsuffixed
`deepseek/deepseek-v4.1-flash` is a different, older model that also answers 200 — never "fix" the pin by
dropping the suffix.
