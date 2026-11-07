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
