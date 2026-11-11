# Engine gate and sweep verification

How to tell whether an engine image row is real evidence, how to audit a sweep
row by row, and how to prove a Dockerfile still builds. Load this when a sweep
is green but the binaries look unproven, when an engine row fails its binary
check, or when you must publish from a PR.

## What a green row must prove

Two independent things:

1. **The binary answers.** At least one probed flag (`--version`, `-h`,
   `--help`, `-V`) must exit 0. A `probe: device` policy is NOT a blanket pass:
   it may only carry a cell named in the exemption list in
   `scripts/engine_image.py`, and every entry states its measured reason. Never
   widen that list to make a row green; disable the cell instead.
2. **The version is a version.** The entrypoint `detect` line must match a
   semantic version, or `pin <sha7+>` for an engine whose upstream prints no
   version. Rejected: `0.0.0` (a wheel that never stamped a version) and a
   timestamped server log line such as
   `0.00.000.331 I srv  llama_server: initializing ...`. Some forks print that
   line and then the real version on the next line, so select the version line
   in `detect` (`--version 2>&1 | grep -E '^version:'`) rather than dropping the
   flag.

### The identity trap

`decide()` is keyed by `(engine, variant)`. A call that omits them defaults to
empty and turns an exempt cell into "not exempt" — the failure text even reads
`<engine>/<variant> binary … is NOT on the device-only exemption list` with an
empty name. Grep every `decide(` call site when you change the signature:
`scripts/engine_image.py::binary_file_works` (used by `test_image` AND by
`push`), plus `tests/test_engine_version.py`, are separate callers of the same
check and can disagree about one image. Make the function refuse a
`policy="device"` verdict that arrives without the identity.

`make engine-gate-report` prints the census from the committed params —
`flag-proven` / `device-exempt` (with its reason) / `disabled` — plus each
cell's `detect` line. Use it instead of reading 27 logs to learn what the
matrix will actually prove.

## Audit a sweep row by row

Per-row logs work for a COMPLETED job while its run is still in progress, but
only through the API — `gh run view --job --log` refuses until the whole run
completes:

```bash
RUN=<run-id>; REPO=<owner>/<repo>
gh run view "$RUN" --repo "$REPO" --json jobs \
  --jq '.jobs[]|select(.name|startswith("engine-build-"))|"\(.databaseId)\t\(.name)\t\(.conclusion)"' |
while IFS=$'\t' read -r jid name concl; do
  gh api "repos/$REPO/actions/jobs/$jid/logs" --allow-escape-sequences 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*m//g' \
    | grep -aE "binary |answers|NO ANSWER|exempt|entrypoint detect|OK image test|FAIL" | tail -6
  echo "^^ $name ($concl)"
done
```

Reading it: `answers ->` on a documented flag is genuine proof; `NO ANSWER` on
EVERY flag means the row leaned on the device exemption; `installed 0.0.0` or
`installed 0.00.000.xxx I srv …` means the version half is broken although the
row is green.

## A pull is not a build

`make build-engine` first tries to satisfy the tag: a local image, else
`docker pull <registry>/<name>:<pinned>-<paramhash>-<arch>`, and on success it
prints `available -> no rebuild` and returns 0. The tag hashes the variant's
params (including `detect`), the Dockerfile, the entrypoint and the runner, so
unchanged inputs pull the published artifact — which proves the artifact
exists, not that the Dockerfile compiles TODAY (the base image tag and pip/uv
resolution move independently). Compile with
`make build-engine ENGINE=<id> ARCH=<arch> FORCE=1`.

## Publish from a same-repo head, never a fork

`ci.yml` runs `make push-engine` on every pull_request. A fork head's token is
read-only, so the row fails with `denied: installation not allowed to Write
organization package` AFTER its build and `test-engine-stage` passed. Any change
touching `containers/engines/params/*.json`, the Dockerfiles, `entrypoint.sh` or
`engine_runner.py` therefore cannot go green from a fork.

Workflow: push the branch to the upstream repo and open the PR with a
same-repo head (`--head <branch>`), which gets a write token. Check runs are
pinned per sha, so after switching heads add a NEW commit (an empty commit is
enough) — otherwise the earlier fork run's failing checks still attach to the
same sha and the PR reads red.

## Dispatched sweeps, queueing and matrix scope

`engine-build.yml` builds and verifies; it publishes only when `push=true`. Its
rows come from `make engine-build-matrix` (the committed params), so only a
params-touching change puts engine rows into a `pull_request` run — a
harness-only change runs zero rows, which is how a broken published-image
target can hide.

Concurrency: a constant `concurrency.group` with
`cancel-in-progress: false` makes a narrow dispatch (`engine=… arch=…`) sit
`pending` with ZERO jobs and no runner until a full sweep finishes —
indistinguishable from a broken dispatcher. Key the group by the selection for
build-only runs, and keep every publishing run in one shared group so two
pushes cannot race on the same `:<arch>` tag.

Verify a dispatcher by running it on a branch that exists in the upstream repo
(`gh workflow run <workflow>.yml --repo <owner>/<repo> --ref <branch> -f …`); a
fork-only ref cannot be dispatched.

## Prove a GPU image on a real host

With the driver installed and CDI devices present (`nvidia-ctk cdi list`
answers):

```bash
docker run --rm --device nvidia.com/gpu=all --entrypoint bash <tag> \
  -c 'mlx_lm.server --help >/dev/null; echo "help exit=$?"'
docker run --rm --device nvidia.com/gpu=all --entrypoint python3 <tag> \
  -c 'import mlx.core as mx; print("device:", mx.default_device())'
make test-engine ENGINE=<id> ARCH=<arch>      # tiny model + OpenAI chat on the GPU
```

Without the device the same import fails with `ImportError: libcuda.so.1`,
which is exactly why the flags exit 1 on a GPU-less runner — evidence the image
is fine, not that the cell is verified. Read the FULL `--version` output before
concluding a fork has no version flag: it can print a log line, the real
version, and a build line, all with exit 0.
