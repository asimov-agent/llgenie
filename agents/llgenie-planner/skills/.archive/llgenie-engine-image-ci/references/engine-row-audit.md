# Auditing an engine-build / engine-image matrix run (is the green real?)

Use when a sweep reports success and you need to know what each row actually proved, when an engine row is
red and you must tell a harness defect from an engine defect, or when changing the gate itself.

## 1. Get the per-row truth table, not the summary

`gh run view <run> --log` on a 27-row matrix is unusable. Iterate the jobs and extract only the verdict lines:

```bash
gh run view <run> --repo <owner>/<repo> --json jobs \
  --jq '.jobs[]|select(.name|startswith("engine-build-"))|"\(.databaseId)\t\(.name)"' \
| while IFS=$'\t' read -r id name; do
    echo "===== $name"
    gh run view --repo <owner>/<repo> --job "$id" --log 2>/dev/null \
      | grep -aE "binary [a-z_./-]+ \(documented|: answers ->|NO ANSWER|policy: device|entrypoint detect|OK image test|FAIL |passed|failed" \
      | sed 's/^[^\t]*\t[^\t]*\t//'
  done > /tmp/audit.txt
```

Classify each row by what the lines show:

| shape in the log | what it proves |
|---|---|
| a documented flag `answers ->` with exit 0 | the binary works |
| every flag `NO ANSWER (exit 1)` yet `OK image test` | only that the FILE exists (a `probe: device` exemption) |
| `entrypoint detect: … installed 0.0.0` | the package metadata is a placeholder — no version proof |
| `entrypoint detect: … 0.00.000.272 I srv …` | a timestamped LOG line taken for a version |
| `FAIL push … denied: installation not allowed to Write organization package` | the gate passed; only publishing was refused (fork head) |

## 2. Read a finished job's log while the run is still going

`gh run view --job <id> --log` refuses until the whole run completes. For a job that already has a
conclusion:

```bash
gh api repos/<owner>/<repo>/actions/jobs/<id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -aE "OK image test|FAIL|denied|entrypoint detect" | tail
```

`--allow-escape-sequences` is required, and dropping ANSI codes first is what makes the grep readable.

## 3. Tell the three failure classes apart before fixing anything

1. **Engine defect** — the binary genuinely cannot answer (missing dependency, import error at
   `line 1, in <module>`). Fix the engine's install or its documented flags.
2. **Harness defect** — the step never reached the image: bare `python3 -m pytest` on the runner
   (`No module named pytest`), a test needing env vars the job does not set, a path that only exists on the host.
   Fix the make recipe to use the container seam (`$(TEST_RUN)`, `$(ENGINE_TEST_RUN)`, `$(call engine_test,…)`).
3. **Permission/plumbing** — `denied: … Write organization package` on a fork head, a tag computed from stale
   params, a row the matrix never created. Fix the workflow or the head, not the engine.

## 4. Gate rules a green row must satisfy

- **At least one probed flag exits 0.** `probe: device` is not an exemption by itself: keep an explicit named
  list of the cells whose CLI cannot import without the device, each with its measured reason, and fail any
  other cell that answers nothing — the failure should name the remedy (list it deliberately, or disable it).
- **The `detect` line must prove a version shape**: a semver, or `pin <sha7+>` for an engine whose upstream
  never prints one. Refuse the `0.0.0` placeholder and a timestamped server log line, and *ignore* a log stamp
  rather than rejecting the whole output — several CLIs print one before the real version.
- **A wheel's `__version__` and its distribution metadata can disagree** (a ROCm sglang wheel reports `0.0.0`
  while cuda reports the real version). Prefer the CLI's own version subcommand; otherwise read
  `importlib.metadata` and fall back to the pinned sha when the value is a placeholder.
- **Fix the detect at the source (the engine skill), then regenerate the params.** The image bakes
  `params.json` and the tag hashes the params, so a stale image keeps reporting its old detect until rebuilt.

## 5. PR head rules for engine changes

- Engine-param changes must come from a **same-repo branch**: every `pull_request` run publishes
  (`make push-engine`), and a fork head carries a read-only token, so `engine-image-*` fails after a passing
  build and test. Push the branch to the upstream repo and open the PR from there.
- Check runs are pinned per **sha**: re-pushing the same commit from a different head keeps the old failing
  checks attached. Add a commit so the PR is judged on its own run.
- Verify the pipeline, not the diff: `gh pr checks <n>` with no `pending`, plus each touched engine's own
  `OK image test` line.

## 6. Proving a binary by hand (GPU host)

```bash
docker pull ghcr.io/<owner>/llgenie/<name>:<pinned>-<hash>-<arch>
docker run --rm --device nvidia.com/gpu=all --entrypoint bash <tag> -c '<binary> --help; echo rc=$?'
docker run --rm --device nvidia.com/gpu=all --entrypoint python3 <tag> -c 'import mlx.core as mx; print(mx.default_device())'
make test-engine ENGINE=<id> ARCH=<arch>   # serves a tiny model through the image and chats
```

Without the device the same image usually fails at import (`libcuda.so.1: cannot open shared object file`) —
that is the GPU-less-runner condition, not a broken image. Run the flag you are about to call "unsupported"
before changing any manifest, and prefer the engine's own `detect`/version subcommand over a guess.
