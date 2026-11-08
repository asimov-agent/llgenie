# Publishing committed engine image pins ("publish OR drop")

When an issue's acceptance is "publish each image pin OR drop the variant", the fix can be a
workflow dispatch rather than a committed code change. Decide and drive it this way.

## Decide publish-vs-drop by CONSUMERS, not by pin name

Dropping a `cuda` variant removes that engine from every cuda host. Check whether the engine has
a real cuda consumer before dropping: several engines are `cuda`+`rocm` only, so dropping `cuda`
removes the engine entirely, and the core engine's cuda build is load-bearing. If any of the four
pins has a live cuda consumer, `drop` is the wrong fix for it — publish instead. Say which engines
are droppable and which are not in the claim comment; do not silently pick one option.

## Publishing is a workflow dispatch

The sanctioned publish path is the engine-build workflow, which has push and GHCR-write perms.
Dispatch it (collaborator-with-write passes its guard):

```bash
gh api repos/<owner>/<repo>/actions/workflows/engine-build.yml/dispatches -X POST \
  -f 'ref=main' -f 'inputs[engine]=<engine>' -f 'inputs[arch]=cuda' -f 'inputs[push]=true' \
  --repo <owner>/<repo>
```

- Dispatch by **file path** (`workflows/engine-build.yml`), not the workflow `-f name=` — the
  display name carries an em-dash and the name shorthand mangles.
- `-f 'inputs[engine]=x'` (inline `=`) is required: `--input`/`-F 'push=true'` tries to read a file
  named `push=true`, and a JSON body must nest everything under an `"inputs"` object.

Shorter equivalent when dispatching a specific branch (no `inputs[...]` nesting):

```bash
gh workflow run engine-build.yml --repo <owner>/<repo> --ref <branch> \
  -f engine=<engine> -f arch=<arch> -f push=false
```

## A full default sweep = dispatch with ONLY `ref` (empty-string inputs 422)

To prove a "default sweep is green" acceptance, dispatch the WHOLE set at the workflow defaults
(`engine=""`, `arch=""`, `push=false`) — not a narrowed cell. Passing the empty values explicitly
fails: `-f engine='' -f arch='' -f push=false` returns `422 Invalid request. "arch", "engine",
"force", "model", "push" are not permitted keys.` Omit every input and pass only the ref — the
workflow's own `default: ""` / `false` then apply:

```bash
gh api repos/<owner>/<repo>/actions/workflows/engine-build.yml/dispatches -X POST -f 'ref=<branch>'
```

Dispatch it on the **PR branch head**, NOT `main`: a `workflow_dispatch` builds the code at the
dispatched ref, so on the PR branch the run exercises YOUR fix (e.g. `DEFAULT_CPU_ONLY={"vllm"}`),
which is exactly what a "default sweep excludes the GPU cells" acceptance asserts. A run on `main`
proves pre-fix behaviour, not the change — the witness would be worthless.

Confirm the dispatched run landed on the intended head before claiming the witness exists:

```bash
gh run list --workflow engine-build.yml --limit 5 \
  --json databaseId,status,headBranch,headSha,event,startedAt \
  --jq '.[] | "\(.databaseId) \(.status) \(.event) @\(.headSha[0:12]) \(.headBranch)"'
```

`gh run list --json` fields are camelCase (`createdAt`, `headSha`, `startedAt`, `databaseId`); a
snake_case name like `created_at` errors `Unknown JSON field` and prints the valid list — rename
the field, do not silently drop it.

## When the PR-trigger's `ci-verdict` blocks the auto-dispatch: dispatch the cell DIRECTLY

The `engine-build-pr-trigger` fires on PR sync and only dispatches `push=true` after its own
`ci-verdict` job reads the guard green. If the guard reds on the DESIGNED self-red (e.g.
`check-pr-acceptance` waiting on a reviewer verdict), `ci-verdict` is `failure` and the push=true
build is **never dispatched** — the acceptance run you need for the issue does not exist yet. Do
not wait for it or conclude the change is unverified. Read the acceptance criterion: an item
phrased `engine-build <engine> arch=<arch> push=false is green` is satisfied by dispatching the
build leg yourself with `push=false` (a build-and-verify — no GHCR publish, no merge, safe).
Dispatch it at the deepened head, then prove it green from the cell's own log. `push=false` runs do
not join the serialized publish concurrency group, so they can run alongside.

## The registry build cache is WRITTEN only on a push build — CI's build leg never seeds it

`scripts/engine_image.py` `_buildx` writes the layer cache (`--cache-to …:buildcache-<variant>`)
**only** in the `push and REGISTRY` branch. The plain local branch does `--cache-from` (read) and
never `--cache-to` (write). So in `engine-build.yml` the build leg (`make build-engine ENGINE=…
ARCH=…`, no `PUSH`) is cache-READ-only, and the later `make push-engine` leg runs `engine_image.py
push` on the ALREADY-BUILT local image — it does not rebuild, so it never runs `--cache-to` either.
Consequence: a variant whose only successful build would come from a `PUSH=1` build that PUSHES
(the exact run that is timing out) never gets a warm cache ref, and every CI attempt rebuilds the
editable install + GPU kernels cold and hits the per-cell time limit again. When a v0.33/cuda/rocm
cell times out while one that has a published cache does not, the fix is to let the build leg
WRITE the cache without publishing a tag (a `CACHEWRITE`/`PUSH` split on `build-engine`) — prove
that seeding is the difference before attributing the timeout to the compile itself.

## PITFALL: rapid back-to-back push dispatches cancel each other

Every `push=true` run joins ONE global push concurrency group. Dispatching several in quick
succession does NOT queue them all: only one acquires a real job, and the siblings end `cancelled`
with **zero jobs** — observed even with `cancel-in-progress: false`. A cancelled-with-no-jobs run
never built anything; its pin stays 404 forever.

Drive publishes **strictly one at a time**: dispatch engine A, wait for its run to reach
`completed` (or its pin to resolve 200), THEN dispatch engine B. If a sibling was cancelled,
re-dispatch it **solo** after the group frees — never re-batch. A background driver that polls the
run status and only then dispatches the next engine is the reliable shape.

## Verify the publish by GHCR manifest, per engine

A run going green is not the proof; the manifested pin is. Query GHCR with a per-engine bearer
token (pin resolution is what the acceptance names). Send a PERMISSIVE `Accept` covering both OCI
and Docker v2 manifest types — pinning only the OCI type makes a Docker-v2 image resolve as a
phantom or 404:

```python
import json, urllib.request
with urllib.request.urlopen('https://ghcr.io/token?scope=repository:<owner>/<repo>/<engine>:pull') as r:
    tok = json.load(r)['token']
req = urllib.request.Request(f'https://ghcr.io/v2/<owner>/<repo>/<engine>/manifests/<pin>',
    headers={'Authorization': f'Bearer {tok}',
             'Accept': 'application/vnd.oci.image.index.v1+json,'
                       'application/vnd.oci.image.manifest.v1+json,'
                       'application/vnd.docker.distribution.manifest.list.v2+json,'
                       'application/vnd.docker.distribution.manifest.v2+json'})
# 200 = published, 404 = not
```

**A 200 status alone is not proof — read the body.** Confirm the response is a real image: a
`schemaVersion: 2` manifest with a `config.digest` (`sha256:…`) and `layers`. Print
`status + Content-Type + body head` and eyeball the config digest; a 200 that returns a head/
error blob, or the wrong media type, is not a pushed image.

## The two acceptance gates: pin resolves AND the liveness check stops naming it

When the issue's acceptance is "the arch check reports 0 not-published", the gate to satisfy is the
committed launcher check, not just the raw 200:

```bash
python3 scripts/check_engine_launchers.py check --check-registry --arch cuda
# tail: "4 ok, 7 stale, 1 missing, 3 not published (arch cuda)"
```

The `N not published (arch <arch>)` summary and the per-engine `NOT PUBLISHED <engine>: … resolves
no manifest` rows ARE acceptance-2. Cite the before→after count (e.g. 4→3 when one engine publishes)
and name the engines still in the list. (The `STALE` rows are a different class — a launcher tag vs
params-computed tag mismatch — off this finding's acceptance unless the issue names them.)

## Prove a build is progressing, not hung (live logs 404 until completion)

A long CUDA compile looks like a stall if you only check run `status`. Do not interpret a missing
log as a hang: the per-job log endpoint (`/actions/jobs/<id>/logs`) returns `BlobNotFound` until the
job completes. Prove forward motion from the job's step timeline instead:

```bash
gh api repos/<owner>/<repo>/actions/runs/<run>/jobs \
  --jq '[.jobs[]|select(.name|startswith("engine-build"))|{status,step:[.steps[]|select(.status=="in_progress")|.name][0],t:.started_at}]'
```

A step that advanced (e.g. `Free disk` → `make build-engine … ARCH=cuda`) with a recent `started_at`
is a live build. A background driver polling run status is the reliable shape for the serialized
publishes; keep exactly ONE driver alive (kill stale ones) so strata/vllm are not double-dispatched.

## A run that ends `failure` can still have published

The build/push legs precede the serve/install/host-verify legs. A pin that resolves 200 while the
run's overall conclusion is `failure` means the publish leg (`push-engine`) succeeded and a LATER
leg reddened. Common env-only red: the install leg fails `cuda host without the NVIDIA CDI spec`
because the runner has no GPU/CDI — that is not a publish failure. Report the pin resolution as the
delivered evidence and name the post-push leg that reddened; do not re-run to chase an env-red leg
that the acceptance does not require.

When the publish path is the whole fix, the branch/PR carries the evidence and the record — a
publish leaves no source diff, so the change→note trio / PR body must cite each pin's 200 and the
run id per engine.
