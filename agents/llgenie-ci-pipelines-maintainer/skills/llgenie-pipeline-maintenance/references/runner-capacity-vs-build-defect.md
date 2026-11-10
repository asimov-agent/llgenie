# A red is capacity or code — read the error line, not the colour

## Distinguishing the two

A cell that dies because the runner was taken away shows, in the job log:

```
##[error]The runner has received a shutdown signal. This can happen when the runner
  service is stopped, or a manually started runner is canceled.
##[error]Process completed with exit code 143.
```

(`143` = SIGTERM, `137` = SIGKILL/OOM.) Critically it has **no** build-failure line —
no `#N ERROR: process "/bin/sh -c ..." did not complete successfully: exit code: 1`
and no `make: *** [Makefile:...: <target>] Error 1`.

A code/build defect **always** emits those lines. So the discriminating test is:

```
gh run view <run> -R asimov-agent/llgenie --log --job <jobid> | grep -iE 'ERROR: process|Error 1'
```

- matches → build/code defect (e.g. `RuntimeError: operator torchvision::nms does not exist`,
  an ABI/pin problem) — a peer lane's fix, report it, do not take it.
- no match, and the failure lands ~20–40 min into a long build → **runner capacity kill**
  (the default `ubuntu-latest` box is ~7 GB; a vllm cuda compile exceeds it).

Corroborate with siblings in the same run: if `rocm` (or `cpu`) SUCCEEDED in the same
matrix, the params/Dockerfile/entrypoint set is sound and only the heavy cell was killed.

## Why it matters in this lane

Never treat a capacity red as green or "watched". Do not recommend rebuilding the killed
cell on the same runner — it will SIGTERM again. The correct peer advice is: dispatch the
cells proven sound now, and track runner-sizing as a separate item.

## A flat threshold cannot guard heterogeneous items — gate per-item, from a committed table

A single constant (`DISK_FLOOR_GB`, a timeout, a retry count) applied to a matrix of unequal
rows is a **false-green for the largest row**. The tell is a cell that *passes* the gate and
then dies later with a different error (a headroom check passing at "107 GiB free" and an
`ENOSPC` seventeen minutes into the build on a 145 GiB host). Never answer that with a bigger
constant — the next heavier engine re-breaks it and every light cell pays the cost.

Fix shape (this lane owns it when the gate is a workflow/make/matrix file):

1. The **producer** emits the requirement per row: `scripts/engine_image.py` `matrix()` carries
   `disk_floor_gb` (same pattern for a per-row `timeout_min` or `runner`). The table is
   committed code — `OVERSIZED_DISK_GB = {("tensorrt-llm","cuda"): 120, ...}` — never a
   workflow `env:` constant nobody can see from the matrix.
2. The **consumer** reads `${{ matrix.<field> }}` (here `LLGENIE_DISK_FLOOR_GB: ${{ matrix.disk_floor_gb }}`)
   so the oversized cell fails FAST with the readable verdict (`df` line) instead of dying
   minutes later under a generic ENOSPC.
3. **Out-of-scope items are ABSENT from the table, never given a number** — a rocm cell scoped
   elsewhere stays unlisted with the issue named in a comment; giving it a floor silently makes
   it "watched".
4. **Mutation-prove both directions** before trusting it: a new test must go RED when you revert
   the workflow to the flat constant **and** RED when the oversized row's field is dropped
   (default 30), then GREEN clean. A test only ever run on the fixed tree proves nothing.

## "Passes alone, fails in the sweep" is resource contention, not a build defect

A cell that FAILS in the full parallel matrix but SUCCEEDS in a narrow single-cell dispatch
(e.g. `tensorfold-cuda`: flag probe fails at `max-parallel 20`, passes in a one-cell run) is
the parallel-resource class, not a code red. Confirm with the sibling timing: cells that start
in the same second and diverge (one fails, one passes) share the runner pool, not the source.

- Do **not** report that cell as a product defect or "fixed" by the disk change — it is a
  separate work item under the same issue's umbrella; say so and keep it open.
- Corroborate each failing cell independently. Reading the run's per-cell matrix (`gh api
  repos/<o>/<r>/actions/runs/<id>/jobs` → filter `matrix.*` / job names) gives the honest
  "N of M passed" table; that table — not the run badge — is what an issue asking for "the
  matrix's real per-engine result" wants quoted, with each failing cell's own log line.



## engine-build.yml runner sizing

- `.github/workflows/engine-build.yml` hardcodes `runs-on: ubuntu-latest` on the build
  matrix job; there is no per-row runner selection.
- `scripts/engine_image.py` `matrix()` emits `{engine, backend, variant, test, disk_floor_gb}`
  (plus a `none` placeholder row) — it carries a **per-row disk floor** but still **no runner field**.
- Therefore routing one heavy cell (vllm `cuda`) to a larger/self-hosted runner is a
  **workflow + matrix-shape change** (add a per-row `runner`/`runs_on` to the matrix and
  read `runs-on: ${{ matrix.runner }}`), not a one-line edit.
- It is only actionable once a suitable runner exists. `gh api repos/<repo>/actions/runners`
  returns **403 for the bot token**; the repo itself records "no AMD host has verified the
  result yet" for llama.cpp rocm. Confirm provisioning with the owner before opening the PR.

## Existing precedent in-tree

`scripts/engine_image.py` already carries a `DEVICE_ONLY`-style dict documenting "long GPU
build > 50 min on hosted runners" exceptions (llama.cpp-prism rocm, #103) — i.e. the
project treats hosted-runner timeouts as a known limitation with a written reason, not as a
silent pass.
