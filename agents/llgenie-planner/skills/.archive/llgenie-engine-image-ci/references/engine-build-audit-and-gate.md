# Auditing a build sweep, and what the binary gate must prove

Use when a dispatched `engine-build` sweep is green (or partly red) and you need to know what each row
actually proved, when a narrowing dispatch appears to do nothing, or when the gate's strictness is in
question.

## Audit a sweep row by row, without reading 27 logs

Enumerate the run's build jobs, then pull only the lines that carry a verdict into a workspace file:

```bash
out=$WORKSPACE/audit-<run>.txt; : > "$out"
gh run view <run> --repo <owner>/<repo> --json jobs \
  --jq '.jobs[]|select(.name|startswith("engine-build-"))|"\(.databaseId)\t\(.name)"' \
| while IFS=$'\t' read -r id name; do
    echo "===== $name" >> "$out"
    gh run view --repo <owner>/<repo> --job "$id" --log 2>/dev/null \
      | grep -aE "binary [,a-z_./-]+ \(documented|: answers ->|NO ANSWER|policy: device|entrypoint detect|OK image test|FAIL |passed|failed" \
      | sed 's/^[^\t]*\t[^\t]*\t//' >> "$out"
  done
```

Then classify each row — do not trust the run's green:

| class | evidence in the log |
|---|---|
| flag-proven | a documented flag `answers ->` (exit 0, non-empty) |
| device-exempt | **every** probe `NO ANSWER (exit 1)` yet `OK image test` — the row leaned on `detect` |
| broken version | `entrypoint detect` line carries a log stamp (`0.00.000.272 I srv …`) or `0.0.0` |
| disabled | absent from the matrix, listed in `DISABLED` with an issue |

`gh run view --job <id> --log` refuses until the RUN completes ("logs will be available when it is
complete"), so audit finished runs; to understand a failure mid-run, use the job's step list
(`--json jobs --jq '.jobs[]|select(.name==X)|.steps[]'`) to see which stage stopped.

## A narrowing dispatch that sits with zero jobs is a concurrency queue, not a bug in dispatch

A workflow with `concurrency: {group: <constant>, cancel-in-progress: false}` serialises EVERY run in that
group. A second dispatch (`engine=one, arch=one`) is then created `pending` with **0 jobs and no runner**
until the first finishes — indistinguishable from a dispatcher that does not work. Check `status` +
`(.jobs|length)` before hunting the workflow file; the fix is to key the group by the inputs the run
differs by, keeping one shared group for anything that publishes (two pushes must not race on the same
`:arch` tag).

## `make build-engine` pulling is the hash cache doing its job

The build is keyed by `<pinned-ref>-<hash of Dockerfile+params>-<arch>`; `build()` first calls
`_available(tag)`, which tries `docker pull <registry>/<name>:<tag>` and, on success, retags locally and
returns `available -> no rebuild`. That is the published artifact for byte-identical inputs — not a fake
build. It compiles only when the tag is absent (new pin/params), or with `FORCE=1`. A hash-tag hit still
says nothing about a moved base image or a live package index, so a sweep that never forces cannot prove
the Dockerfiles still build; check whether the workflow exposes a `force` input before promising that.

## What the binary gate must prove (and the traps that make it lie)

1. **At least one probed flag must exit 0.** A `probe: device` policy that accepts a cell whose flags all
   failed is a blanket pass — confiers rode green with every probe at exit 1. If a cell genuinely cannot
   import without its device, keep it in a NAMED exemption table where each entry states the measured
   reason and an issue, and make any unlisted `device` cell red.
2. **A version must look like a version.** `re.search(r"\d+\.\d+", detect_output)` is satisfied by a
   timestamped log line (`0.00.000.272 I srv …`) and by `0.0.0`. Accept a semver, or `pin <sha7+>` for an
   engine whose upstream prints none, and *ignore* log-stamp spans rather than rejecting the whole output
   — a CLI can print a stamp line and then a real `version: 0.5.0-dev (build …)` line, and rejecting the
   text throws that version away.
3. **A `detect` that greps the wrong line is the usual root cause** once (2) is in place: prefer
   `--version 2>&1 | grep -E '^version:'` over the first line of output, and prefer the installed
   distribution's version over a module `__version__` that a vendor wheel leaves at `0.0.0`.
4. Give the census a command (`make <something>-report`) that prints each cell as flag-proven / exempt /
   disabled from the committed params, so the honest shape of a sweep is one command, not an audit.

## Prove a GPU-only cell on a host, not by assumption

Hosted runners have no GPU, so a `probe: device` cell can never prove itself there. On a host with an
NVIDIA card and CDI devices (`nvidia-ctk cdi list`):

```bash
docker pull <registry>/<name>:<tag>
docker tag  <registry>/<name>:<tag> <name>:<tag>
# the exact probe CI could not run:
docker run --rm --device nvidia.com/gpu=all --entrypoint bash <name>:<tag> -c '<binary> --help; echo exit=$?'
# which device the framework actually selects (mlx/cuda answers Device(gpu, 0); without the device it is
# `ImportError: libcuda.so.1` — that ImportError is WHY the flags exit 1 on a GPU-less runner):
docker run --rm --device nvidia.com/gpu=all --entrypoint python3 <name>:<tag> \
  -c 'import mlx.core as mx; print(mx.default_device())'
# end to end through the repo's own seam (downloads a tiny model, serves, chats):
make test-engine ENGINE=<id> ARCH=<arch>
```

Run these BEFORE writing a diagnosis into an issue or a PR body. A claim like "this fork does not
implement `--version`" is cheap to check and expensive to retract: `--version` may exit 0 and carry the
real version on line 2 while line 1 is a log stamp. If the published artifact disproves your fix, correct
the issue body, the PR body and the work record in the same batch — a wrong root cause left standing is
worse than a later commit.

## Monitoring long pipelines without burning the session

Poll `gh pr checks <n>` (or `gh run view <id> --json status`) in a background loop that exits when nothing
is `pending`; guard against the false settle where `gh pr checks` briefly returns no rows — require at least
one `pass`/`fail` line before treating the absence of `pending` as done. Range each poll with a bounded
`sleep 60` loop, and report the real job conclusions, never a prediction.
