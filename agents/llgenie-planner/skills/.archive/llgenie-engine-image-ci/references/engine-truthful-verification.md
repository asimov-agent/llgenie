# Truthful engine verification, and where a publishing PR can live

Depth for llgenie engine-CI work. Measured on real runs and real published images.

## A green row proves only what its strongest assertion shows

`scripts/engine_image.py` has two judges, and both used to be satisfiable without the binary working:

* `decide(documented, verdicts, policy, engine=…, variant=…)` — the flag judge. Every documented flag must
  answer, and **at least one probed flag must exit 0**. `policy="device"` is NOT an exemption by itself: only
  a `(engine, variant)` named in the reasoned `DEVICE_ONLY` list may lean on the entrypoint `detect`. An
  unlisted device cell is red and names both remedies (`DEVICE_ONLY` with a reason, or `DISABLED`).
* `version_proof(text)` — the version judge. Accept a semver (`0.5.21`, `0.32.0+cpu`, `0.7.0-dev`) or
  `pin <sha7+>`. Refuse a timestamped log line (`0.00.000.272 I srv  llama_server: initializing ...`), the
  placeholder `0.0.0`, and anything that merely "contains digits".

Classify every audited row by what it proves — `flag-proven`, `device-exempt` (needs the GPU: file plus a
version-shaped detect), `disabled` — and quote `make engine-gate-report`'s census instead of rereading 27 logs.

When the gate hardens, an EXISTING test usually asserts the old escape (`test_a_device_probe_is_contained_…`).
Update that test to assert BOTH directions (listed cell passes with its reason, unlisted cell is red); never
delete it, or the suite stops documenting the rule.

## A CLI may print noise BEFORE its version — read every line

`llama.cpp-laurentzuijdwijk --version` prints three lines and exits 0:

```
0.00.000.331 I srv  llama_server: initializing ...
version: 0.5.0-dev (build 11364, commit 3c75be02f)
built with GNU 13.3.0 for Linux x86_64
```

A `detect` of `{binary} --version` surfaces only the first line. Fix the `detect` to select the `version:`
line; do NOT drop the flag or substitute a pin — the flag answers. Measure in the PUBLISHED image before
rewriting an engine's flags: the version is regularly on a later line.

## `detect` is baked into the image, and it IS in the tag hash

`params.json` is copied into the build context, so `entrypoint.sh detect` comes from the image, and the
variant's params (including `detect`) are hashed into the tag (`<pin8>-<hash8>-<variant>`). Changing `detect`
therefore moves the tag and forces a real build; a run that logs `available -> no rebuild` is testing the OLD
detect. Never conclude a detect fix works from a pull of an unchanged tag.

## Which step actually failed

```bash
gh run view <run> --repo O/R --json jobs --jq '.jobs[]|select(.conclusion=="failure")|{name,id:.databaseId}'
gh api "repos/O/R/actions/jobs/<job-id>/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -aE "OK image test|entrypoint detect|FAIL|denied" | tail
```

`gh run view --job <id> --log` refuses while the RUN is still in progress; the jobs API works for any
completed job, so a matrix can be diagnosed while it is still draining. For many rows, loop the job ids and
grep the decisive lines into one file, then read that file — never pull 27 full logs into context.

## A fork-headed PR cannot publish engine images

The engine matrix runs `make push-engine` on every `pull_request` run. A fork head carries a read-only token,
so the job builds, passes `test-engine-stage`, then dies at the push:

```
denied: installation not allowed to Write organization package
[engine-image] FAIL push ghcr.io/<owner>/llgenie/<name>:<tag>
```

That is a permission, not a defect in the change. For any PR touching engine params or Dockerfiles: push the
branch into the BASE repo, open the PR from that same-repo head (no `owner:` prefix), close the fork-headed PR
with a comment naming the denial, and add one commit (empty is fine) before re-heading — check runs are pinned
per sha, so the old fork run's red checks otherwise keep the new PR red. A `push` event on a feature branch
does not run the pipeline (CI's `push` trigger is `main` only), so pushing the branch proves nothing alone.

## GPU-only cells: verify on a host, not from the run

`NO ANSWER (exit 1)` on every flag of a GPU engine is usually the missing driver at import, not a broken image:

```bash
docker run --rm --device nvidia.com/gpu=all --entrypoint python3 <img> \
  -c "import mlx.core as mx; print(mx.default_device())"    # with the device: Device(gpu, 0)
                                                            # without it: ImportError: libcuda.so.1
make test-engine ENGINE=<id> ARCH=<variant>                  # serves a tiny model, chats through the SDK
```

Report it as host evidence, never as CI coverage: hosted runners have no GPU, so a `device-exempt` row stays
that way until a GPU runner exists.
