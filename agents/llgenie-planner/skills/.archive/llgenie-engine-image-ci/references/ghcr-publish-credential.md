# Which credential can publish an image to GHCR, and how to prove it

Pointer: this file covers the agent/test/engine image PUBLISH credential. The
read-only side (hash tags, `ensure`/`pull`, the engine matrix) is in SKILL.md.

## A successful `docker login` proves nothing about pushing

GHCR validates the user/PAT pair and mints a scoped token at
`GET https://ghcr.io/token?service=ghcr.io&scope=repository:<owner>/llgenie/<name>:push`.
If the credential has no `write:packages`, the exchange still succeeds but the
token carries no push access, and the FIRST real write fails:

```
403 {"errors":[{"code":"DENIED","message":"permission_denied: The token provided does not match expected scopes."}]}
```

So a publish job that dies in seconds with its build step SKIPPED is a credential
verdict, not a build failure. Read it with
`gh run view <run> --log | grep -E 'push-check|login'` before touching the image.

The cheapest real write is an **empty blob upload** — `POST /v2/<path>/blobs/uploads/`
with no body: a refusal costs nothing, a success leaves no layer. That is what
`make agent-image-push-check` does; trust it over `docker login` succeeding.

## Which credential a publish job uses

Every image here is published with `secrets.GITHUB_TOKEN` plus
`permissions: packages: write`, logging in as `github.actor`:

```yaml
env: { LLGENIE_REGISTRY: ghcr.io/${{ github.repository_owner }} }
permissions: { contents: read, packages: write }
run: echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin
```

- Do NOT invent or reuse a PAT secret for a package push. If a job logs in with
the owner PAT and the registry refuses it, switch that job to the
`GITHUB_TOKEN` shape above — the same credential the sibling publish path already
uses successfully, which is the proof it works.
- `asimov-agent` is a **user** account (`gh api users/asimov-agent --jq .type` →
`User`), so "Create organization package" denials do not apply to this namespace.
Do not hunt for an org permission; read the registry's own message instead.

## The invariant worth a test: login secret == pre-flight secret

A job that logs in with credential A and proves the push with credential B looks
configured and can never publish. Lock it hermetically: parse the workflow, take
`re.search(r"secrets\.([A-Z_]+)", login_step["run"])` and the `GHCR_TOKEN` value
of the pre-flight step, and assert the two names are equal and equal
`GITHUB_TOKEN`, that the login user is `github.actor`, and that
`permissions.packages == "write"`.

## Live-verifying a workflow fix BEFORE the merge

`workflow_dispatch` only accepts refs that exist in `asimov-agent/llgenie`, so a
fork-only branch cannot be dispatched. In this checkout `git remote -v` is
`origin = asimov-agent/llgenie` (upstream) and `fork = andyholst/llgenie`:

```bash
git push -u fork feat/<branch>                 # the PR head (always)
git push -u origin feat/<branch>               # only when you need a dispatchable ref
gh workflow run <workflow>.yml --repo asimov-agent/llgenie --ref feat/<branch>
gh run list --repo asimov-agent/llgenie --workflow <workflow>.yml --limit 2
```

A green pre-merge run (`push-check … empty upload accepted (202)`) is stronger
evidence than any stub, and cheap when the image's hash tag already exists: the
publish step inspects the manifest and no-ops instead of rebuilding. Quote the
run's real lines in the PR body; never claim a live verification you did not run.

## Before implementing: look for a stranded fix

A commit pushed to a branch AFTER that branch's PR merged reaches no PR and no
CI-on-base, and nothing flags it. Search first:

```bash
git log --all --oneline -S"<symbol-or-target>"   # is the change already written somewhere?
git merge-base --is-ancestor <sha> origin/main   # …and is it on main?
gh pr list --repo asimov-agent/llgenie --head <branch> --state all --json number,state
```

If the commit exists on a branch whose PR is already MERGED, do not re-derive the
work by hand: cut a fresh worktree off `origin/main`, `git cherry-pick -n <sha>`,
then add the OpenSpec change, README and agent-wiki record the stranded commit
lacks, and verify before pushing.

## Two mechanical pitfalls of this flow

- **`make openspec-new` writes as root.** The CLI runs in the container with
`-u root`, so the new `openspec/changes/<name>/` is root-owned and `write_file`
fails `Permission denied`. Fix at once:
`sudo chown -R $(id -u):$(id -g) openspec/changes/<name>`.
- **`check-nonphony` does not exist** — `.PHONY` coverage is enforced by
`make check-wiring`. Gate set for a pipeline change: `make lint`,
`check-workflows`, `check-docs`, `check-wiring`, `check-dispatch-forms`,
`check-pr-hygiene`, `check-pr-authors`, `openspec-validate NAME=<name>`, then
`make test-unit` — whose Hugging Face README link probes can flake on HTTP 429,
so re-run `tests/test_trend_pick.py` in isolation before blaming your diff.
