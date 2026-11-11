# Publishing the llgenie agent (Hermes) image

The bots run in `ghcr.io/<owner>/llgenie/agent:<hash>`. Everything below is about getting that exact
tag onto GHCR from GitHub Actions, and proving it afterwards.

## The tag is a hash of the build inputs, not of the commit

`python3 scripts/ci_images.py ref agent` prints the tag from `containers/agent/Dockerfile` +
`scripts/install_hermes_ci.sh` + `scripts/install_nerve_ci.sh` + `scripts/agent_jev_preflight.sh` +
the test image's tag. A README, a workflow, or a test change does **not** move it; a pin or
install-script change does. Run it before publishing, on the branch **and** on the base branch, and
publish the tag the bots will actually ask for after merge.

## Dispatch from a ref the upstream repo has

`workflow_dispatch --ref` resolves inside the repo that owns the workflow, so a fork-only branch
cannot be dispatched. Push the feature branch to `origin` (upstream — a branch, never `main`), then:

```bash
gh workflow run publish-agent-image.yml --repo <upstream> --ref <branch> -f force=false
gh run list --repo <upstream> --workflow publish-agent-image.yml --limit 1 \
  --json databaseId,status,headBranch --jq '.[]|"\(.databaseId) \(.status) \(.headBranch)"'
```

Publishing from the branch is what lets a pin reach the bots the moment the PR merges: the merged
commit's inputs are the same bytes, so the tag is already on GHCR.

## The credential: use the one that provably works elsewhere

The publish job's own pre-flight (`make agent-image-push-check`) is the verdict:

```
[ci-images] push-check <owner>/llgenie/agent: the credential CANNOT push (403):
{"errors":[{"code":"DENIED","message":"permission_denied: The token provided does not match expected scopes."}]}
```

That means the PAT has no `write:packages`. Do not widen the PAT path — mirror the credential the
sibling publish already uses (`ci.yml`'s `ci-images` job, which publishes `llgenie/test`):

```yaml
permissions: { contents: read, packages: write }
run: echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin
```

and hand the **same** secret to the push-check (`GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}`). Lock it in
a test asserting login secret == push-check secret == `GITHUB_TOKEN`: a job that logs in with A and
proves B is green on the wrong credential.

A justifying comment is not evidence — check it against the live repo. A header blaming an
"organization package" denial is void when the namespace is a **user** account
(`gh api /users/<owner> --jq .type`).

## "Package not found" is usually the wrong endpoint

`GET /user/packages/container/<owner>%2F<name>/versions` lists the **authenticated user's** packages.
For another account's namespace it 404s and reads like "never published" even when the tag exists.
Use the owner-scoped endpoint:

```bash
gh api "/users/<owner>/packages/container/<owner>%2Fagent/versions?per_page=5" \
  --jq '.[]|"\(.metadata.container.tags|join(",")) \(.created_at)"'
```

`docker manifest inspect <ref>` succeeding anonymously is an independent check (and tells you the
package is public, which is what a runner needs).

## Prove the published tag, not the local build

`llgenie/agent:latest` on the dev host may be a build from an earlier pin. Pull the tag you just
published and interrogate **that** image:

```bash
docker pull -q <published-ref>
docker run --rm <published-ref> bash -lc 'for k in model provider max_tokens context_window; do \
  printf "%s=" "$k"; hermes config get "model.aliases.<alias>.$k"; done'
```

Report those values. What the tag buys: `ci_images.py ensure agent` pulls instead of rebuilding
Hermes + the Nerve plugin inside every bot job.

## Pitfalls

- `make hermes-smoke` proves a text reply — not the alias's model id, and not tool calling. Read the
  alias config out of the image, and for tool calling run a one-shot with a tool prompt through the
  same alias and look for the tool's own output.
- The push-check runs **before** the build by design; quote its line instead of a later timeout.
  A ~30s run whose later steps are `skipped` is that verdict, never a build problem — change the
  credential, do not re-run or rebuild.
- Before re-fixing a red publish, check the branches: a commit pushed to a branch AFTER that branch's
  PR merged is stranded (not on `main`, no PR carries it). Re-cut off `origin/main` and cherry-pick it
  with its OpenSpec change rather than re-deriving the fix.
- Re-running the publish is a no-op while the hash tag exists; `force=true` re-pushes the same hash,
  it does not create a new one.
